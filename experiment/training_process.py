import os
import sys

sys.path.append(os.path.abspath('..'))

import time
import logging
from torch.multiprocessing import Process

from multiagent_loops.simultaneous_action_rl_loop import self_play_training


def training_process(env, training_agent, self_play_scheme, checkpoint_at_iterations, agent_queue, process_name, results_path):
    """
    :param env: Environment where agents will be trained on
    :param training_agent: agent representation + training algorithm which will be trained in this process
    :param self_play_scheme: self play scheme used to meta train the param training_agent.
    :param checkpoint_at_iterations: array containing the episodes at which the agents will be cloned for benchmarking against one another
    :param agent_queue: queue shared among processes to submit agents that will be benchmarked
    :param process_name: String name identifier
    :param results_path: Directory where results will be saved
    """
    logger = logging.getLogger(process_name)
    logger.setLevel(logging.DEBUG)
    logger.info('Started')
    process_start_time = time.time()

    completed_iterations = 0
    menagerie = []
    for target_iteration in sorted(checkpoint_at_iterations):
        next_training_iterations = target_iteration - completed_iterations

        training_start = time.time()
        (menagerie, trained_agent,
         trajectories) = self_play_training(env=env, training_agent=training_agent,
                                            self_play_scheme=self_play_scheme, target_episodes=next_training_iterations,
                                            menagerie=menagerie, results_path=results_path, iteration=completed_iterations)

        training_duration = time.time() - training_start

        completed_iterations += next_training_iterations

        path = f'{results_path}{process_name}_tp_it{target_iteration}.pt'
        logger.info('Submitted agent at iteration {} :: saving at {}'.format(target_iteration,path))
        agent2queue = trained_agent.clone(path=path)
        agent_queue.put([target_iteration, self_play_scheme, agent2queue])

        logger.info('Submitted agent at iteration {} :: OK'.format(target_iteration))
        logger.info('Training duration between iterations [{},{}]: {} (seconds)'.format(target_iteration - next_training_iterations, target_iteration, training_duration))

        file_name = '{}-{}.txt'.format(self_play_scheme.name,training_agent.name)
        enumerated_trajectories = zip(range(target_iteration - next_training_iterations, target_iteration), trajectories)
        write_episodic_reward(enumerated_trajectories, target_file_path='{}/{}'.format(results_path,file_name))

        # Updating:
        training_agent = trained_agent
    logger.info('All training completed. Total duration: {} seconds'.format(time.time() - process_start_time))


def write_episodic_reward(enumerated_trajectories, target_file_path):
    with open(target_file_path, 'a') as f:
        for iteration, trajectory in enumerated_trajectories:
            player_1_average_reward = sum(map(lambda t: t[2][0], trajectory)) / len(trajectory) # TODO find a way of not hardcoding indexes
            f.write('{}, {}\n'.format(iteration,player_1_average_reward))


def create_training_processes(training_jobs, createNewEnvironment, checkpoint_at_iterations, agent_queue, results_path):
    """
    :param training_jobs: Array of TrainingJob namedtuples containing a training-scheme, algorithm and name
    :param createNewEnvironment: OpenAI gym environment creation function
    :param checkpoint_at_iterations: array containing the episodes at which the agents will be cloned for benchmarking against one another
    :param agent_queue: queue shared among processes to submit agents that will be benchmarked
    :returns: array of process handlers, needed to join processes at the end of experiment computation
    """
    # TODO Create experiment directory tree structure much earlier, and all together
    episodic_reward_directory = '{}/episodic_rewards'.format(results_path)
    if not os.path.exists(episodic_reward_directory):
        os.mkdir(episodic_reward_directory)

    logger = logging.getLogger('CreateTrainingProcesses')
    logger.setLevel(logging.DEBUG)
    logger.info('Training {} jobs: [{}]. '.format(len(training_jobs), ', '.join(map(lambda job: job.name, training_jobs))))
    ps = []
    for job in training_jobs:
        p = Process(target=training_process,
                    args=(createNewEnvironment(), job.algorithm, job.training_scheme,
                          checkpoint_at_iterations, agent_queue, job.name, episodic_reward_directory))
        ps.append(p)
    logger.info("All training jobs submitted")
    return ps
