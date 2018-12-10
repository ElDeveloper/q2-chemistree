# ----------------------------------------------------------------------------
# Copyright (c) 2016-2018, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import subprocess
import os

from ._semantics import MGFDirFmt, SiriusDirFmt, ZodiacDirFmt, CSIDirFmt


def run_command(cmd, output_fp, verbose=True):
    if verbose:
        print("Running external command line application. This may print "
              "messages to stdout and/or stderr.")
        print("The command being run is below. This command cannot "
              "be manually re-run as it will depend on temporary files that "
              "no longer exist.")
        print("\nCommand:", end=' ')
        print(" ".join(cmd), end='\n\n')

    with open(output_fp, 'w') as output_f:
        subprocess.run(cmd, stdout=output_f, check=True)


def artifactory(sirius_path: str, parameters: list, java_flags: str = None,
                constructor=None):
    artifact = constructor()
    if not os.path.exists(sirius_path):
        raise OSError("SIRIUS could not be located")
    sirius = os.path.join(sirius_path, 'sirius')

    initial_flags = os.environ.get('_JAVA_OPTIONS', '')
    if java_flags is not None:
        # append the flags to any existing options
        os.environ['_JAVA_OPTIONS'] = initial_flags + ' ' + java_flags
    cmdsir = ([sirius, '-o', artifact.get_path()] + parameters)
    run_command(cmdsir, os.path.join(str(artifact.path), 'stdout.txt'))

    if java_flags is not None:
        os.environ['_JAVA_OPTIONS'] = initial_flags

    return artifact


def compute_fragmentation_trees(sirius_path: str, features: MGFDirFmt,
                                ppm_max: int, profile: str,
                                tree_timeout: int = 1600,
                                maxmz: int = 600, n_jobs: int = 1,
                                num_candidates: int = 75,
                                database: str = 'all',
                                ionization_mode: str = 'auto',
                                java_flags: str = None) -> SiriusDirFmt:
    '''Compute fragmentation trees for candidate molecular formulas.

    Parameters
    ----------
    sirius_path : str
        Path to Sirius executable (without including the word sirius).
    features : MGFDirFmt
        MGF file for Sirius
    ppm_max : int
        allowed parts per million tolerance for decomposing masses
    profile: str
        configuration profile for mass-spec platform used
    tree_timeout : int, optional
        time for computation per fragmentation tree in seconds. 0 for an
        infinite amount of time
    maxmz : int, optional
        considers compounds with a precursor mz lower or equal to this
        value (int)
    n_jobs : int, optional
        Number of cpu cores to use. If not specified Sirius uses all available
        cores
    num_candidates: int, optional
        number of fragmentation trees to compute per feature
    database: str, optional
        search formulas in given database
    ionization_mode : str, optional
        Ionization mode for mass spectrometry. One of `auto`, `positive` or
        `negative`.
    java_flags : str, optional
        Setup additional flags for the Java virtual machine.

    Returns
    -------
    SiriusDirFmt
        Directory with computed fragmentation trees
    '''

    # qiime2 will check that the only possible modes are positive, negative or
    # auto
    if ionization_mode in {'auto', 'positive'}:
        ionization_flag = '--auto-charge'
    elif ionization_mode == 'negative':
        ionization_flag = '--ion=[M-H]-'

    params = ['--quiet',
              '--initial-compound-buffer', str(1),
              '--max-compound-buffer', str(32), '--profile', str(profile),
              '--database', str(database),
              '--candidates', str(num_candidates),
              '--processors', str(n_jobs),
              '--trust-ion-prediction',
              '--maxmz', str(maxmz),
              '--tree-timeout', str(tree_timeout),
              '--ppm-max', str(ppm_max),
              os.path.join(str(features.path), 'features.mgf')]

    return artifactory(sirius_path, params, java_flags, SiriusDirFmt)


def rerank_molecular_formulas(sirius_path: str,
                              fragmentation_trees: SiriusDirFmt,
                              features: MGFDirFmt,
                              zodiac_threshold: float = 0.95, n_jobs: int = 1,
                              java_flags: str = None) -> ZodiacDirFmt:
    """Reranks molecular formula candidates generated by computing
       fragmentation trees

    Parameters
    ----------
    sirius_path : str
        Path to Sirius executable (without including the word sirius).
    fragmentation_trees : SiriusDirFmt
        Directory with computed fragmentation trees
    features : MGFDirFmt
        MGF file for Sirius
    zodiac_threshold : float
        threshold filter for molecular formula re-ranking. Higher value
        recommended for less false positives (float)
    n_jobs : int, optional
        Number of cpu cores to use. If not specified Sirius uses all available
        cores
    java_flags : str, optional
        Setup additional flags for the Java virtual machine.

    Returns
    -------
    ZodiacDirFmt
       Directory with reranked molecular formulas
    """

    params = ['--zodiac', '--sirius',
              str(fragmentation_trees.get_path()),
              '--thresholdfilter', str(zodiac_threshold),
              '--processors', str(n_jobs),
              '--spectra', os.path.join(str(features.path), 'features.mgf')]

    return artifactory(sirius_path, params, java_flags, ZodiacDirFmt)


def predict_fingerprints(sirius_path: str, molecular_formulas: ZodiacDirFmt,
                         ppm_max: int, n_jobs: int = 1,
                         fingerid_db: str = 'pubchem',
                         java_flags: str = None) -> CSIDirFmt:
    """Predict molecular fingerprints

    Parameters
    ----------
    sirius_path : str
        Path to Sirius executable (without including the word sirius).
    molecular_formulas : ZodiacDirFmt
        Directory with the re-ranked formulae.
    ppm_max : int
        Allowed parts per million tolerance for decomposing masses.
    n_jobs : int, optional
        Number of cpu cores to use. If not specified Sirius uses all available
        cores.
    fingerid_db : str, optional
        Search structure in given database.
    java_flags : str, optional
        Setup additional flags for the Java virtual machine.

    Returns
    -------
    CSIDirFmt
        Directory with predicted fingerprints.
    """

    params = ['--processors', str(n_jobs), '--fingerid',
              '--fingerid-db', str(fingerid_db), '--ppm-max', str(ppm_max),
              molecular_formulas.get_path()]
    return artifactory(sirius_path, params, java_flags, CSIDirFmt)
