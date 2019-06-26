"""
setuptools setup.cfg reading hacks/functions.
"""

import os
try:
    import configparser
except ImportError:
    # python2 (also prevents dict-like access)
    import ConfigParser as configparser

try:
    from setuptools._vendor.packaging.requirements import Requirement
except BaseException:
    from pkg_resources._vendor.packaging.requirements import Requirement

from setuptools.config import ConfigHandler, read_configuration

# TODO: still got to decide what to do about this...
try:
    from setuptools._vendor.packaging.version import Version as packaging_Version
except ImportError:
    packaging_Version = None


from . import log_message


SETUP_CFG = "setup.cfg"  # rename PKG_CONFIG or something?


def tidyextras(x):
    r = Requirement(x)
    if len(r.extras) > 1:
        x = r.name + "[" + ','.join(sorted(r.extras)) + "]"
    else:
        x = r.name
    return x


def get_setup_args(must_contain=[]):
    """Get dict from setup.py - augmented with setup.cfg"""
    from setup import setup_args

    # adding in any info from setup.cfg
    cfg = read_configuration(SETUP_CFG)
    setup_args.update(**cfg['metadata'])
    setup_args.update(**cfg['options'])

    for arg in must_contain:
        assert arg in setup_args
    return setup_args

###########################


# TODO: what do people who install dependencies via conda actually do?
# Have their own list via other/previous development work? Read from
# travis? Translate from setup.py?  Read from meta.yaml? Install from
# existing anaconda.org conda package and then remove --force?  Build
# and install conda package then remove --force?
def _get_dependencies(groups, all_extras=False, pypi_only=True):
    """get dependencies from setup.cfg"""
    meta = get_setup_args()
    deps = []
    if all_extras:
        assert groups is None
        extras = meta.get('extras_require', {})
        groups = set(groups).union(set(extras))
    for group in groups:
        if group in ('install_requires', 'tests_require'):
            deps += meta.get(group, [])
            extras = False
        else:
            # TODO: it's ok to not fail for missing install_requires,
            # tests_require, i.e. standard ones. Not ok to not fail for missing
            # extras_require e.g. I try doit develop_install -o recommended but
            # recommended does not exist that should be an error
            deps += meta.get('extras_require', {}).get(group, [])
            extras = True

        if not pypi_only:
            # re-reading every time is stupid
            deps += read_requires_beyond_pypi(extras, group)

    if not pypi_only:
        if 'python' not in [Requirement(d).name for d in deps]:
            pyver = meta.get('python_requires', '')
            deps += ['python %s' % pyver]

    return deps


def get_dependencies(groups, all_extras=False, pypi_only=True):
    return " ".join('"%s"' % dep for dep in _get_dependencies(
        groups, all_extras=all_extras, pypi_only=pypi_only))


######################################################################
# setup.cfg reading hacks

# TODO: can i use more of setuptools config parsing?  There was some
# reason I didn't use setuptools.config.read_configuration, but I
# can't remember what it was now. (I think it was to do with needing a
# % sign for the git format (autover), but then that breaking some version
# of config reading.) Replace bit by bit and see what happens?

# hack for now, just to cut down code duplication. supports only
# limited things.
def _get_from_setup_cfg(pyctdev_section, key, outertype, innertype=None):
    log_message("Attempting to read '%s.%s' from %s...",
                pyctdev_section, key, SETUP_CFG)
    assert outertype is not None

    # duplicates some earlier configparser stuff (which doesn't
    # support py2; need to clean up)
    config = configparser.ConfigParser()
    config.read(SETUP_CFG)

    if pyctdev_section not in config.sections():
        log_message("...'%s' not found", pyctdev_section)
        return outertype()

    try:
        raw = config.get(pyctdev_section, key)
        log_message("...found %s", raw)
    except configparser.NoOptionError:
        log_message("...'%s' not found", key)
        raw = ''

    if outertype is dict and innertype is list:
        d = ConfigHandler._parse_dict(raw)
        return {k: ConfigHandler._parse_list(d[k]) for k in d}
    elif outertype is dict and innertype is None:
        return ConfigHandler._parse_dict(raw)
    elif outertype is list and innertype is None:
        return ConfigHandler._parse_list(raw)
    else:
        raise


def read_pins():
    return _get_from_setup_cfg('tool:pyctdev', 'pins', dict)


def read_requires_beyond_pypi(extras, group):
    if extras:
        assert group not in ('install_requires', 'tests_require')
    res = _get_from_setup_cfg('tool:pyctdev.requires_beyond_pypi', group, list)
    # TODO: decide about adding python here
    if group == 'install_requires' and not 'python' in [
            Requirement(dep).name for dep in res]:
        res.append('python')
    return res


def read_provides():
    return _get_from_setup_cfg('tool:pyctdev', 'provides', list)


def read_extras_provide():
    return _get_from_setup_cfg('tool:pyctdev', 'extras_provide', dict, list)

# TODO should be using a python fn to get the package name


def get_package_path(sdist=False):
    meta = read_configuration(SETUP_CFG)['metadata']
    version = meta['version']
    name = meta['name']
    if not sdist:
        # TODO: only support universal wheel so far
        pname = name + "-" + version + "-py2.py3-none-any.whl"
    else:
        pname = name + "-" + version + ".tar.gz"
    # TODO: why versioning tool not match python?
    pname = pname.replace("-dirty", ".dirty")
    # TODO: assumption about location
    return os.path.join("dist", pname)


# TODO: is this used much? or it's just to get pyctdev's version?
def parse_version_with_packaging_Version(version):
    global packaging_Version
    if packaging_Version is None:
        # trigger the error here so people know what's wrong.
        from setuptools._vendor.packaging.version import Version as packaging_Version

    return packaging_Version(version)
