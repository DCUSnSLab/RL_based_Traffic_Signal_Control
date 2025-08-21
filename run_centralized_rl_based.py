# -*- coding: utf-8 -*-

import os
import sys
import json
import random
from typing import List, Dict, Any

import numpy as np
import traci

# ===== Stable-Baselines3 / Gymnasium =====
from stable_baselines3 import DQN
from stable_baselines3.common.callbacks import BaseCallback

import gymnasium as gym
from gymnasium.spaces import Box, Discrete
from gymnasium.spaces.utils import flatten, flatten_space

# ===== SUMO-RL =====
from sumo_rl import SumoEnvironment, ObservationFunction, TrafficSignal

# ===== 프로젝트 내 모듈 =====
from Infra import Config_SUMO, Infra, NETWORK_RESULT, SSection
from RunSimulation import RunSimulation


# =========================================================
# 유틸: SUMO_HOME 등록
# =========================================================
if "SUMO_HOME" in os.environ:
    tools = os.path.join(os.environ["SUMO_HOME"], "tools")
    if tools not in sys.path:
        sys.path.append(tools)
else:
    raise RuntimeError("환경변수 SUMO_HOME 이 설정되어 있지 않습니다.")


# =========================================================
# 중앙집중형 래퍼: dict(obs/reward) <-> 단일 obs/스칼라 보상 (Gymnasium Env 상속)
# =========================================================
def _get_obs_space(env, agent_id):
    if hasattr(env, "observation_spaces"):
        obj = env.observation_spaces
        if isinstance(obj, dict):
            return obj[agent_id]
        if callable(obj):
            try:
                maybe = obj()
                if isinstance(maybe, dict):
                    return maybe[agent_id]
            except TypeError:
                pass
            return obj(agent_id)
    raise KeyError(f"observation space not found for agent {agent_id}")

def _get_act_space(env, agent_id):
    if hasattr(env, "action_spaces"):
        obj = env.action_spaces
        if isinstance(obj, dict):
            return obj[agent_id]
        if callable(obj):
            try:
                maybe = obj()
                if isinstance(maybe, dict):
                    return maybe[agent_id]
            except TypeError:
                pass
            return obj(agent_id)
    raise KeyError(f"action space not found for agent {agent_id}")


class CentralizedForDQNEnv(gym.Env):
    """
    Gymnasium Env로 감싼 중앙집중 래퍼
    - obs: dict(agent->obs) -> concat된 1D Box
    - act: Discrete(JOINT_N) -> dict(agent->Discrete)
    - rew: dict -> scalar(mean/sum)
    """
    metadata = {"render_modes": []}

    def __init__(self, base_env: SumoEnvironment, tls_order: List[str], reward_agg: str = "mean"):
        super().__init__()
        self.base_env = base_env
        self.tls_order = list(tls_order)
        self.reward_agg = reward_agg

        # --- 관측 공간 결합 ---
        flat_spaces = []
        self._obs_spaces = {}
        for tls_id in self.tls_order:
            os_ = _get_obs_space(self.base_env, tls_id)
            self._obs_spaces[tls_id] = os_
            flat_spaces.append(flatten_space(os_))
        low = np.concatenate([fs.low for fs in flat_spaces]).astype(np.float32)
        high = np.concatenate([fs.high for fs in flat_spaces]).astype(np.float32)
        self.observation_space = Box(low=low, high=high, dtype=np.float32)

        # --- 합성 Discrete 액션 ---
        self._act_spaces = {}
        self.nvec = []
        for tls_id in self.tls_order:
            aspace = _get_act_space(self.base_env, tls_id)
            assert hasattr(aspace, "n"), f"{tls_id} action space must be Discrete"
            self._act_spaces[tls_id] = aspace
            self.nvec.append(int(aspace.n))
        self.joint_n = int(np.prod(self.nvec, dtype=np.int64))
        self.action_space = Discrete(self.joint_n)

        # 기수법 base: [n2*n3*..., n3*..., ..., 1]
        self.bases = np.array(
            [int(np.prod(self.nvec[i + 1:], dtype=np.int64)) for i in range(len(self.nvec))],
            dtype=np.int64
        )

        # sumo-rl 속성 패스스루 (dt 등 외부 코드에서 참조)
        for k in ("delta_time", "yellow_time", "min_green", "max_green"):
            if hasattr(self.base_env, k):
                setattr(self, k, getattr(self.base_env, k))

    # ===== 내부 유틸 =====
    def _concat_obs(self, obs_dict):
        flats = []
        for tls_id in self.tls_order:
            os_ = self._obs_spaces[tls_id]
            flats.append(flatten(os_, obs_dict[tls_id]).astype(np.float32))
        return np.concatenate(flats, axis=0)

    def _decode_joint(self, a_int: int):
        rem = int(a_int)
        out = []
        for base, n in zip(self.bases, self.nvec):
            val = rem // base % n
            out.append(int(val))
        return out

    # ===== Gymnasium 표준 인터페이스 =====
    def reset(self, *, seed=None, options=None):
        # Gymnasium 규약: (obs, info) 반환
        res = self.base_env.reset()
        if isinstance(res, tuple):
            obs_dict, info = res[0], (res[1] if len(res) > 1 else {})
        else:
            obs_dict, info = res, {}
        obs = self._concat_obs(obs_dict)
        return obs, info

    def step(self, action):
        # Gymnasium 규약: (obs, reward, terminated, truncated, info)
        joint = self._decode_joint(int(action))
        action_dict = {tls_id: joint[i] for i, tls_id in enumerate(self.tls_order)}
        res = self.base_env.step(action_dict)

        if isinstance(res, tuple) and len(res) == 4:
            obs_dict, rew_dict, done_dict, info = res
            terminated = bool(done_dict.get("__all__", False))
            truncated = False
        elif isinstance(res, tuple) and len(res) == 5:
            obs_dict, rew_dict, terminated_dict, truncated_dict, info = res
            terminated = bool(terminated_dict.get("__all__", False))
            truncated  = bool(truncated_dict.get("__all__", False))
        else:
            raise RuntimeError("Unexpected env.step() return format")

        obs = self._concat_obs(obs_dict)
        if self.reward_agg == "sum":
            reward = float(np.sum([rew_dict[t] for t in self.tls_order]))
        else:
            reward = float(np.mean([rew_dict[t] for t in self.tls_order]))
        return obs, reward, terminated, truncated, info

    def close(self):
        self.base_env.close()

    def render(self):
        return None


# ==========================================
# Custom SUMO Env (Infra 연동 + 공유 CO2 보상)
# ==========================================
class CustomSumoEnvironment(SumoEnvironment):
    def __init__(self, simInfra: Infra, **kwargs):
        super().__init__(**kwargs)
        self._cust_step = 0
        self._cust_infra: Infra = simInfra

    def _get_tls_ids(self) -> List[str]:
        tls_ids = getattr(self, "ts_ids", None) or getattr(self, "tls_ids", None)
        if tls_ids:
            return list(tls_ids)
        if hasattr(self, "action_spaces"):
            obj = self.action_spaces
            if isinstance(obj, dict):
                return list(obj.keys())
            if callable(obj):
                try:
                    maybe = obj()
                    if isinstance(maybe, dict):
                        return list(maybe.keys())
                except TypeError:
                    pass
        return list(traci.trafficlight.getIDList())

    def _compute_reward(self):
        # 네트워크 총 CO2(직전 스텝, mg/s) → 모든 TLS에 동일 보상
        total_co2_emission = 0.0
        for vid in traci.vehicle.getIDList():
            total_co2_emission += traci.vehicle.getCO2Emission(vid)
        return {tls_id: -total_co2_emission for tls_id in self._get_tls_ids()}

    def getCustInfra(self):
        return self._cust_infra

    def _sumo_step(self):
        self.sumo.simulationStep()
        self._cust_infra.update()
        self._cust_step += 1


# (선택) 관측을 CO2로 대체하려면 사용 — 학습/평가 모두 동일하게 맞춰야 함
class CO2ObservationFunction(ObservationFunction):
    def __init__(self, ts: TrafficSignal):
        super().__init__(ts)

    def __call__(self) -> np.ndarray:
        cust_infra: Infra = self.ts.env.getCustInfra()
        total_co2_emission = cust_infra.getTotalCO2mg()
        phase_onehot = [1 if self.ts.green_phase == i else 0 for i in range(self.ts.num_green_phases)]
        can_switch = [0 if self.ts.time_since_last_phase_change < self.ts.min_green + self.ts.yellow_time else 1]
        obs = np.array(phase_onehot + can_switch + [total_co2_emission], dtype=np.float32)
        return obs

    def observation_space(self) -> gym.Space:
        dim = self.ts.num_green_phases + 1 + 1
        return Box(low=np.zeros(dim, dtype=np.float32), high=np.full(dim, np.inf, dtype=np.float32))


# 콜백(원하면 로깅 추가)
class EveryStepCallback(BaseCallback):
    def __init__(self, verbose=0):
        super().__init__(verbose)

    def _on_step(self) -> bool:
        return True


# =========================================================
# 표시 전용: TLS 상태 → Infra 섹션에 반영 (외부 제어 없음)
# =========================================================
def load_signal_mapping(path: str) -> Dict[str, Dict[str, Dict[str, bool]]]:

    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    # 기본 빈 매핑(없어도 동작하도록)
    return {}

# =========================================================
# 실행 컨트롤러 (학습된 DQN으로 평가)
# =========================================================
class RunCentralizedDQNControl(RunSimulation):
    def __init__(self, config: Config_SUMO, name: str):
        SumoSeed = random.randint(0, 2_147_483_647)
        super().__init__(config, 'RL_DQL', isExternalSignal=True)

        # (1) base env: 다중 에이전트로 열기
        EnvClass = CustomSumoEnvironment  # CO2 보상 내장
        self.base_env = EnvClass(
            net_file=self.config.scenario_file_rl,
            route_file=self.config.route_file_rl,
            single_agent=False,            # 중앙집중 래퍼 적용 예정
            use_gui=True,
            yellow_time=4,
            min_green=34,
            max_green=60,
            sumo_seed=SumoSeed,
            # observation_class=CO2ObservationFunction,  # 학습 때 사용했다면 주석 해제
            simInfra=self.getInfra()
        )
        print("[RunCentralizedDQNControl] sumo_seed:", SumoSeed)

        # (2) TLS 순서 확정
        res = self.base_env.reset()
        if isinstance(res, tuple):
            obs_dict = res[0]
        else:
            obs_dict = res
        if isinstance(obs_dict, dict):
            detected_tls = list(obs_dict.keys())
        else:
            detected_tls = list(traci.trafficlight.getIDList())

        # 학습 시 저장한 tls_order.json이 있으면 사용
        self.tls_order = detected_tls
        tls_order_path = os.path.join("save_models", "tls_order.json")
        if os.path.isfile(tls_order_path):
            with open(tls_order_path, "r", encoding="utf-8") as f:
                saved_order = json.load(f)
            self.tls_order = [t for t in saved_order if t in detected_tls]

        print("[RunCentralizedDQNControl] TLS_ORDER:", self.tls_order)

        # (3) 중앙집중형 단일-에이전트 래퍼
        self.env = CentralizedForDQNEnv(self.base_env, tls_order=self.tls_order, reward_agg="mean")

        # (4) 모델 로드
        self.model = DQN.load("dqn_model_centralized_min34.zip", env=self.env, device="cuda")

        # (5) 표시용 신호 매핑 로드(선택)
        self.signal_mapping = load_signal_mapping("signal_mapping.json")

        # 내부 상태
        self.isStop = False

    def preinit(self):
        pass

    # 합성 행동 디코드(로깅 전용) — 신호 변경 X
    def _decode_joint_action(self, a_int: int) -> List[int]:
        return self.env._decode_joint(int(a_int))

    def run_simulation(self):
        obs, _ = self.env.reset()
        terminated = False
        truncated = False
        total_reward = 0.0
        step = 0

        dt = getattr(self.env, "delta_time", 1)
        maxstep = int(4800 / dt)

        while (not self.isStop) and (step <= maxstep) and (not (terminated or truncated)):
            # 추론 시에는 deterministic=True 권장
            action, _ = self.model.predict(obs, deterministic=True)

            # (선택) 로깅: 합성 → TLS별 액션(신호 변경 X, 기록만)
            # per_tls_actions = self._decode_joint_action(int(action))
            # for tls_id, a in zip(self.tls_order, per_tls_actions):
            #     print(f"[STEP {step}] {tls_id} -> phase {a}")

            obs, reward, terminated, truncated, info = self.env.step(action)
            total_reward += float(reward)
            step += 1


        self.isStop = True
        try:
            self.env.close()
        finally:
            try:
                traci.close(False)
            except Exception:
                pass