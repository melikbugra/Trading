import pandas as pd
import numpy as np
from financia.envs.trading_env import TradingEnv
# Trigger Registration
import financia.envs 
from rl_baselines.policy_based.ppo import PPO
import os
from types import SimpleNamespace

def train_agent(dataset_path, model_name, timesteps=50000):
    print(f"Loading data from {dataset_path}...")
    if not os.path.exists(dataset_path):
        print("Dataset not found. Skipping.")
        return

    df = pd.read_parquet(dataset_path)
    print(f"Data loaded. Shape: {df.shape}")
    
    # Train/Val Split
    split_idx = int(len(df) * 0.9) 
    train_df = df.iloc[:split_idx]
    val_df = df.iloc[split_idx:]
    
    # Create Environment
    env = TradingEnv(train_df)
    # Patch env.spec for library compatibility - using Registered ID
    env.spec = SimpleNamespace(id="TradingEnv-v0")
    
    # Initialize Agent (PPO)
    print("Initializing PPO Agent...")
    model = PPO(
        env=env,
        eval_env_kwargs={'df': val_df}, # kwargs for gym.make('TradingEnv-v0')
        network_type="mlp",
        network_arch=[256, 256],
        time_steps=timesteps,
        learning_rate=0.0001, # Lower LR for noisy market data stability
        batch_size=256,       # Larger batch size for stable gradients (CPU optimized)
        gamma=0.99,
        entropy_coef=0.01,
        device='cpu',
        plot_train_sores=True,
    )
                
    # Train
    print("Starting Training...")
    model.train()
    
    # Save
    os.makedirs("models", exist_ok=True)
    
    # Save logic with library naming
    model.save(folder="models", checkpoint=model_name)
    
    # Rename to desired path
    generated_path = f"models/TradingEnv-v0_PPO_cpu_{model_name}.ckpt"
    target_path = f"models/{model_name}.ckpt"
    if os.path.exists(generated_path):
        os.rename(generated_path, target_path)
        print(f"Model renamed and saved to {target_path}")
    else:
        print(f"Warning: Could not find generated model at {generated_path}")
    
    return model

if __name__ == "__main__":
    # Train Short Term Agent
    print("--- Training SHORT Term Agent (Hourly) ---")
    train_agent("data/dataset_short.parquet", "ppo_short_agent", timesteps=1_000_000)
