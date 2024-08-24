import os
import sys
import logging
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
if "SUMO_HOME" in os.environ:
    tools = os.path.join(os.environ["SUMO_HOME"], "tools")
    sys.path.append(tools)
else:
    sys.exit("Please declare the environment variable 'SUMO_HOME'")

from stable_baselines3.dqn.dqn import DQN
from env import SumoEnvironment
from traffic_signal import TrafficSignal as traffic_signal

log_directory = 'logs'
if not os.path.exists(log_directory):
    os.makedirs(log_directory)

import torch
from model_utils import save_model
def co2_emission_reward(traffic_signal):
    return traffic_signal._combined_reward_with_section()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=os.path.join(log_directory, 'application.log'),  # 'logs/application.log' 경로
    filemode='w'
)
env = SumoEnvironment(
    net_file="../New_TestWay/test.net_mergy.xml",
    single_agent=True,
    route_file="../New_TestWay/generated_flows_pm_test.xml",
    out_csv_name="../New_TestWay/dqn/",
    use_gui=False,
    num_seconds=15000,
    yellow_time=4,
    min_green=5,
    max_green=60,
    reward_fn=co2_emission_reward,
    delta_time=5,
    num_episodes = 100
    ,
)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = DQN(
    env=env,
    policy="MlpPolicy",
    learning_rate=1e-3,
    learning_starts=0,
    buffer_size=50000,
    train_freq=1,
    target_update_interval=500,
    exploration_initial_eps=0.7,
    exploration_fraction=0.3,
    exploration_final_eps=0.03,
    verbose=1,
    device=device,
)
# Train the model
model.learn(total_timesteps=(env.num_seconds // env.delta_time) * env.num_episodes)

# Save final model
save_model(model, "../output/model/", episode=env.num_episodes, model_type="final")