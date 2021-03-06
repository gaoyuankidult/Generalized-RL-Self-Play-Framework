import os
import signal
import logging

from collections import namedtuple
from collections import Counter
from torch.multiprocessing import Process

from benchmark_match_play import benchmark_match_play_process

RecordedAgent = namedtuple('RecordedAgent', 'iteration training_scheme agent')
BenchmarkingJob = namedtuple('BenchmarkingJob', 'iteration recorded_agent_vector')


def match_making_process(expected_number_of_agents, benchmarking_episodes, createNewEnvironment, agent_queue, matrix_queue, pool):
    """
    Process in charge of keeping a record of the trained agents
    received from the training processes through the agent queue.
    This process creates a benchmarking processes for each combination
    of RecordedAgents (iteration, training scheme, agent)
    It shuts itself down once it doesn't expect any new recorded agents.

    :param expected_number_of_agents: Number of agents that the process will wait for before shuting itself down
    :param benchmarking_episodes: Number of episodes that each benchmarking process will run for
    :param createNewEnvironment: OpenAI gym environment creation function
    :param agent_queue: Queue reference shared among processes to submit agents that will be benchmarked
    :param matrix_queue: Queue reference sent to benchmarking process, where it will put the bencharmking result
    :param pool: ProcessPoolExecutor shared between benchmarking_jobs to carry out benchmarking matches
    """
    logger = logging.getLogger('MatchMaking')
    logger.setLevel(logging.DEBUG)
    logger.info('Started')

    # Initialize variables
    received_agents = 0
    recorded_agents = []
    recorded_benchmarking_jobs = []

    benchmarking_child_processes = []
    while True:
        iteration, training_scheme, agent = agent_queue.get() # wait_for_agent(agent_queue)

        received_agents += 1
        logger.info('Received ({},{},{}). {}/{} received'.format(iteration, training_scheme.name, agent.name, received_agents, expected_number_of_agents))

        recorded_agents.append(RecordedAgent(iteration, training_scheme, agent))

        processes = [create_benchmark_process(benchmarking_episodes, createNewEnvironment,
                                              match, pool, matrix_queue, match_name)
                     for match_name, match in calculate_new_benchmarking_jobs(recorded_agents, recorded_benchmarking_jobs, iteration)]

        for p in processes:
            benchmarking_child_processes.append(p)

        check_for_termination(received_agents, expected_number_of_agents, benchmarking_child_processes, pool)


def check_for_termination(received_agents, expected_number_of_agents, child_processes, pool):
    """
    Checks if process should be killed because all processing has been submitted.
    That is, all expected agents have been received and all benchmarking
    child processes have been created.

    :param received_agents: Number of agents received so far
    :param expected_number_of_agents: Number of agents that the process will wait for before shuting itself down
    :param child_processes: Benchmarking jobs still running
    :param pool: ProcessPoolExecutor shared between benchmarking_jobs to carry out benchmarking matches
    """
    if received_agents >= expected_number_of_agents:
        [p.join() for p in child_processes]
        if pool is not None : pool.shutdown()
        os.kill(os.getpid(), signal.SIGTERM)


def calculate_new_benchmarking_jobs(recorded_agents, recorded_benchmarking_jobs, iteration_filter):
    """
    Given the current set of recorded agents,
    checks which ones haven't been been benchmarked against one another
    and computes new jobs to be sent for execution.

    :param recorded_agents: array of received RecordedAgent
    :param recorded_benchmarking_jobs: Array of benchmarking_jobs that have kill
    :param iteration filter: Filters recorded agents on iteration because agents can only be benchmarked against those of same iteration
    """
    filtered_recorded_agents = [RecordedAgent(recorded_agent.iteration, recorded_agent.training_scheme, recorded_agent.agent.clone()) for recorded_agent in recorded_agents if recorded_agent.iteration == iteration_filter]
    for recorded_agent_1 in filtered_recorded_agents:
        for recorded_agent_2 in filtered_recorded_agents:
            benchmark_name = 'Benchmark:({},{}) vs ({},{}). iteration: {}'.format(recorded_agent_1.training_scheme.name,
                                                                                  recorded_agent_1.agent.name,
                                                                                  recorded_agent_2.training_scheme.name,
                                                                                  recorded_agent_2.agent.name,
                                                                                  iteration_filter)
            job = BenchmarkingJob(iteration_filter, [recorded_agent_1, recorded_agent_2])
            if not is_benchmarking_job_already_recorded(job, recorded_benchmarking_jobs):
                recorded_benchmarking_jobs.append(job)
                yield benchmark_name, job


def is_benchmarking_job_already_recorded(job, recorded_benchmarking_jobs):
    """
    Checks if BenchmarkingJob is a contained within the list of already
    recorded BenchmarkingJobs. For this an equality onf BenchmarkingJobs is defined
    :param job: BenchmarkingJob which is being checked to see if it has already been recorded
    :param recorded_benchmarking_jobs: List of recoreded BenchmarkingJobs
    """
    job_equality = lambda job1, job2: job1.iteration == job2.iteration and Counter(job1.recorded_agent_vector) == Counter(job2.recorded_agent_vector)
    return any([job_equality(job, recorded_job) for recorded_job in recorded_benchmarking_jobs])


def create_benchmark_process(benchmarking_episodes, createNewEnvironment, benchmark_job, pool, matrix_queue, name):
    """
    Creates a benchmarking process for the precomputed benchmark_job.
    The results of the benchmark will be put in the matrix_queue to populate confusion matrix

    :param benchmarking_episodes: Number of episodes that each benchmarking process will run for
    :param createNewEnvironment: OpenAI gym environment creation function
    :param benchmark_job: precomputed BenchmarkingJob
    :param pool: ProcessPoolExecutor shared between benchmarking_jobs to carry out benchmarking matches
    :param matrix_queue: Queue reference sent to benchmarking process, where it will put the bencharmking result
    :param name: BenchmarkingJob name identifier
    """
    benchmark_process = Process(target=benchmark_match_play_process,
                                args=(benchmarking_episodes, createNewEnvironment,
                                      benchmark_job, pool, matrix_queue, name))
    benchmark_process.start()
    return benchmark_process
