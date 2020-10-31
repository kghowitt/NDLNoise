# coding: utf-8

import argparse
import dataclasses
import logging
import multiprocessing
from datetime import datetime
from random import random
from typing import List

from InstrumentedChild import InstrumentedNDChild
from domain import ColagDomain
from output_handler import write_results
from utils import progress_bar

logging.basicConfig(level=logging.INFO)

DOMAIN = ColagDomain()


class ExperimentDefaults:
    """Defaults paramters for experiment."""
    rate = 0.9
    conservativerate = 0.0005
    numberofsentences = 500000
    numechildren = 100
    noise_levels = [0, 0.05, 0.10, 0.25, 0.50]


@dataclasses.dataclass
class ExperimentParameters:
    languages: List[int]
    noise_levels: List[float]
    learningrate: float
    conservative_learningrate: float
    num_sentences: int
    num_echildren: int
    num_procs: int


@dataclasses.dataclass
class TrialParameters:
    """ The parameters for a single echild simulation """
    language: int
    noise: float
    rate: float
    conservativerate: float
    numberofsentences: int


class Language:
    English = 611
    French = 584
    German = 2253
    Japanese = 3856


class LanguageNotFound(Exception):
    """Raised when a user attempts to read a language that does not exist in domain
    file.

    """
    pass


def run_child(language, noise, rate, conservativerate, numberofsentences):

    aChild = InstrumentedNDChild(rate, conservativerate, language)

    for i in range(numberofsentences):
        if random() < noise:
            s = DOMAIN.get_sentence_not_in_language(grammar_id=language)
        else:
            s = DOMAIN.get_sentence_in_language(grammar_id=language)
        aChild.consumeSentence(s)

    return aChild


def run_trial(params: TrialParameters):
    """ Runs a single echild simulation and reports the results """
    logging.debug('running echild with %s', params)

    params = dataclasses.asdict(params)  # type: ignore
    then = datetime.now()
    child = run_child(**params)  # type: ignore
    now = datetime.now()

    results = {'timestamp': now,
               'duration': now - then,
               'language': child.target_language,
               **child.grammar,
               **params}  # type: ignore

    logging.debug('experiment results: %s', results)

    return results


def run_simulations(params: ExperimentParameters):
    """Runs echild simulations with given parameters across all available
    processors. Returns a generator that yields one result dictionary (as
    returned by run_trial) for each simulation run.

    """

    trials = (
        TrialParameters(language=lang,
                        noise=noise,
                        rate=params.learningrate,
                        numberofsentences=params.num_sentences,
                        conservativerate=params.conservative_learningrate)
        for lang in params.languages
        for noise in params.noise_levels
        for _ in range(params.num_echildren)
    )

    num_trials = (params.num_echildren
                  * len(params.languages)
                  * len(params.noise_levels))

    DOMAIN.init_from_flatfile(params.learningrate,
                              params.conservative_learningrate)

    with multiprocessing.Pool(params.num_procs) as p:
        results = p.imap_unordered(run_trial, trials)
        results = progress_bar(results,
                               total=num_trials,
                               desc="running simulations")
        yield from results


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('-r', '--rate',
                        type=float,
                        default=ExperimentDefaults.rate)
    parser.add_argument('-c', '--cons-rate',
                        type=float,
                        default=ExperimentDefaults.conservativerate)
    parser.add_argument('-e', '--num-echildren',
                        type=int,
                        help='number of echildren per language/noise-level',
                        default=ExperimentDefaults.numechildren)
    parser.add_argument('-s', '--num-sents',
                        type=int,
                        default=ExperimentDefaults.numberofsentences)
    parser.add_argument('-n', '--noise-levels', nargs="+", type=float,
                        default=ExperimentDefaults.noise_levels)
    parser.add_argument('-p', '--num-procs', type=int,
                        help='number of concurrent processes to run',
                        default=multiprocessing.cpu_count())
    parser.add_argument('-v', '--verbose', default=False,
                        action='store_const', const=True,
                        help='Output per-echild debugging info')
    return parser.parse_args()


def main():
    args = parse_arguments()

    logging.info('starting simulation with %s',
                 ' '.join('{}={}'.format(key, val)
                          for key, val in args.__dict__.items()))

    params = ExperimentParameters(
        learningrate=args.rate,
        conservative_learningrate=args.cons_rate,
        num_sentences=args.num_sents,
        noise_levels=args.noise_levels,
        num_procs=args.num_procs,
        num_echildren=args.num_echildren,
        languages=[Language.English,
                   Language.French,
                   Language.German,
                   Language.Japanese])

    results = run_simulations(params)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    write_results('simulation_output', args, results)


if __name__ == "__main__":
    main()
