from .tabular_q_learning import TabularQLearningAlgorithm, TabularQLearningAgent, build_TabularQ_Agent
from .deep_q_network import DeepQNetworkAlgorithm, DeepQNetworkAgent, build_DQN_Agent
from .gym_rock_paper_scissors_agent import MixedStrategyAgent
from .interface import AgentHook

rockAgent     = MixedStrategyAgent(support_vector=[1, 0, 0], name='RockAgent')
paperAgent    = MixedStrategyAgent(support_vector=[0, 1, 0], name='PaperAgent')
scissorsAgent = MixedStrategyAgent(support_vector=[0, 0, 1], name='ScissorsAgent')
randomAgent   = MixedStrategyAgent(support_vector=[1/3, 1/3, 1/3], name='RandomAgent')
