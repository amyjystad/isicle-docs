#from statsmodels.stats.weightstats import DescrStatsW
import pandas as pd
import numpy as np
import pickle
from isicle.geometry import Geometry, XYZGeometry
from isicle.utils import TypedList


def _function_selector(func):
    '''
    Selects a supported reduction function for reducing a set of conformers.

    Parameters
    ----------
    func : str
        Alias for function selection (one of "boltzmann", "simple", "lowest",
        or "threshold").

    Returns
    -------
    func
        Conformer reduction function.

    '''

    func_map = {'boltzmann': boltzmann,
                'simple': simple_average,
                'lowest': lowest_energy,
                'threshold': threshold}

    if func.lower() in func_map.keys():
        return func_map[func.lower()]
    else:
        raise ValueError('{} not a supported reduction function.'.format(func))


def _energy_based(func):
    '''
    Checks whether function employs an energy-based reduction operation.

    Parameters
    ----------
    func : func
        Conformer reduction function.

    Returns
    -------
    bool
        True if energy based, otherwise False.

    '''

    if func in [boltzmann, lowest_energy, threshold]:
        return True

    return False


def reduce(value, func='boltzmann', **kwargs):
    '''
    Combine values according to indicated function.

    Parameters
    ----------
    value : :obj:`~numpy.array`
        Array containing values that will be combined.
    func : str
        Alias for function selection (one of "boltzmann", "simple", "lowest",
        or "threshold").
    **kwargs
        Additional keyword arguments passed to `func`.

    Returns
    -------
    :obj:`~pandas.DataFrame`
        Result of reduction operation.

    '''

    f = _function_selector(func)

    # Energy-based method
    if _energy_based(f):
        energy = kwargs.pop('energy')
        return f(value, energy, **kwargs)

    # Other method
    return f(value, **kwargs)


def boltzmann(value, energy, index=None):
    '''
    Combine values according to a Boltzmann-weighted average.

    Parameters
    ----------
    value : :obj:`~numpy.array`
        Array containing values that will be combined.
    energy : :obj:`~numpy.array`
        Array containing energy values that correspond to entries in `value`.
    index : None or :obj:`~numpy.array`
        Index by which to group values for averaging.

    Returns
    -------
    :obj:`~pandas.DataFrame`
        Result of reduction operation.

    '''

    df = pd.DataFrame({'value': value, 'energy': energy, 'index': -1})

    if index is not None:
        df['index'] = index

    res = []
    for name, group in df.groupby(['index']):
        g = group['energy'] * 627.503
        mn = g.min()
        relG = g - mn
        b = np.exp(-relG / 0.5924847535)
        w = (b / b.sum()) * len(b)

        #ws = DescrStatsW(group['value'], weights=w, ddof=0)
         
        #res.append([name, ws.mean, ws.std, len(group.index)])

    #res = pd.DataFrame(res, columns=['index', 'mean', 'std', 'n'])

    #if index is None:
    #    return res.drop(columns='index').iloc[0]

    #return res


def simple_average(value, index=None):
    '''
    Combine values according to a simple average.

    Parameters
    ----------
    value : :obj:`~numpy.array`
        Array containing values that will be combined.
    index : None or :obj:`~numpy.array`
        Index by which to group values for averaging.

    Returns
    -------
    :obj:`~pandas.DataFrame`
        Result of reduction operation.

    '''

    df = pd.DataFrame({'value': value, 'index': -1})

    if index is not None:
        df['index'] = index

    res = df.groupby(['index'], as_index=False).agg({'value':
                                                     ['mean', 'std', 'count']})
    res.columns = ['index', 'mean', 'std', 'n']

    if index is None:
        return res.drop(columns='index').iloc[0]

    return res


def lowest_energy(value, energy, index=None):
    '''
    Combine values according to lowest energy.

    Parameters
    ----------
    value : :obj:`~numpy.array`
        Array containing values that will be combined.
    energy : :obj:`~numpy.array`
        Array containing energy values that correspond to entries in `value`.
    index : None or :obj:`~numpy.array`
        Index by which to group values for averaging.

    Returns
    -------
    :obj:`~pandas.DataFrame`
        Result of reduction operation.

    '''

    df = pd.DataFrame({'value': value, 'energy': energy, 'index': -1})

    if index is not None:
        df['index'] = index

    res = df.loc[df.groupby('index')['energy'].idxmin()]

    if index is None:
        return res.drop(columns='index').iloc[0]

    return res


def threshold(value, energy, threshold=5, index=None):
    '''
    Combine values with energy below a given threshold according to a simple
    average.

    Parameters
    ----------
    value : :obj:`~numpy.array`
        Array containing values that will be combined.
    energy : :obj:`~numpy.array`
        Array containing energy values that correspond to entries in `value`.
    index : None or :obj:`~numpy.array`
        Index by which to group values for averaging.

    Returns
    -------
    :obj:`~pandas.DataFrame`
        Result of reduction operation.

    '''

    df = pd.DataFrame({'value': value, 'energy': energy, 'index': -1})

    if index is not None:
        df['index'] = index

    df = df.loc[df['energy'] <= threshold, :]

    res = df.groupby(['index'], as_index=False).agg({'value':
                                                     ['mean', 'std', 'count']})
    res.columns = ['index', 'mean', 'std', 'n']

    if index is None:
        return res.drop(columns='index').iloc[0]

    return res


def build_conformational_ensemble(geometries):
    '''
    Create a conformational ensemble from a collection of geometries.

    Parameters
    ----------
    geometries : list of :obj:`~isicle.geometry.Geometry` or related subclass
        Collection of geometry instances.

    Returns
    -------
    :obj:`~isicle.conformers.ConformationalEnsemble`
        Conformational ensemble.

    '''

    return ConformationalEnsemble(geometries)


def load_pickle(path):
    '''
    Load pickled file.

    Parameters
    ----------
    path : str
        Path to pickle.

    Returns
    -------
    :obj:`~isicle.conformers.ConformationalEnsemble`
        Previously pickled :obj:`~isicle.conformers.ConformationalEnsemble`
        instance.

    Raises
    ------
    IOError
        If file cannot be read.
    TypeError
        If file is not a supported class instance.

    '''

    # Load file
    with open(path, 'rb') as f:
        try:
            ensemble = pickle.load(f)
        except pickle.UnpicklingError:
            raise IOError('Could not read file as pickle: {}'.format(path))

    # Check for valid class type
    if isinstance(ensemble, ConformationalEnsemble):
        return ensemble

    # Failure. This is not a ConformationalEnsemble instance
    raise TypeError('Unsupported format: {}.'.format(ensemble.__class__))


def load(path):
    '''
    Load file.

    Parameters
    ----------
    path : str
        Path to file.

    Returns
    -------
    :obj:`~isicle.conformers.ConformationalEnsemble`
        Previously pickled :obj:`~isicle.conformers.ConformationalEnsemble`
        instance.

    '''

    return load_pickle(path)


class ConformationalEnsemble(TypedList):
    '''
    Collection of :obj:`~isicle.geometry.Geometry`, or related subclass,
    instances.

    '''

    def __init__(self, *args):
        '''
        Initialize :obj:`~isicle.conformers.ConformationalEnsemble` instance.

        Parameters
        ----------
        *args
            Objects to comprise the conformational ensemble.

        '''

        super().__init__((Geometry, XYZGeometry), *args)

    def _check_attributes(self, attr):
        '''
        Check if all ensemble members have the supplied attribute.

        Parameters
        ----------
        attr : str
            Attribute to check.

        Raises
        ------
        AttributeError
            If all members do not have `attr`.

        '''

        if not all(attr in x.get_global_properties() for x in self):
            raise AttributeError('"{}" not found for all conformational '
                                 'ensemble members.'.format(attr))

    def reduce(self, attr, func='boltzmann', **kwargs):
        '''
        Combine attribute values according to indicated function.

        Parameters
        ----------
        attr : str
            Attribute that will be combined.
        func : str
            Alias for function selection (one of "boltzmann", "simple",
            "lowest", or "threshold").
        **kwargs
            Additional keyword arguments passed to `func`.

        Returns
        -------
        :obj:`~pandas.DataFrame`
            Result of reduction operation.

        '''

        f = _function_selector(func)

        # Check for primary attribute
        self._check_attributes(attr)

        # Check for energy attribute
        if _energy_based(f):
            self._check_attributes('energy')

        # Extract value attribute
        value = [x.get_global_properties()[attr] for x in self]

        # Check for index
        if type(value[0]) is dict and 'index' in value[0]:
            index = np.array([x['index'] for x in value]).flatten()
            value = np.array([x[attr] for x in value]).flatten()
            pad = pad = int(len(index) / len(self))
        else:
            index = None
            pad = 1

        # Extract energy attribute
        if _energy_based(f):
            energy = np.array([x.get_global_properties()['energy']['energy'] * pad for x in self])
            energy = energy.flatten()

            # Exectue energy-based method
            return f(value, energy, index=index, **kwargs)

        # Execute other method
        return f(value, index=index, **kwargs)

    # TODO: automatically unpack multiple returned objects
    def _apply_method(self, method, **kwargs):
        '''
        Process conformational ensemble members according to supplied method.

        Parameters
        ----------
        method : str
            Method by which ensemble members will be processed.
        **kwargs
            Keyword arguments passed to `method`.

        Returns
        -------
        :obj:`~isicle.conformers.ConformationalEnsemble` or list
            Result of operation, type depends on `method` return type.

        '''

        # Check for attribute
        if not all(hasattr(x, method) for x in self):
            raise AttributeError('"{}" not found for all conformational '
                                 'ensemble members.'.format(method))

        # Apply method to collection
        result = [getattr(x, method)(**kwargs) for x in self]

        # Return ConformationalEnsemble if correct result type
        try:
            return ConformationalEnsemble(result)

        # Return result as-is
        except:
            return result

    # TODO: automatically unpack multiple returned objects
    def _apply_function(self, func, **kwargs):
        '''
        Process conformational ensemble members according to supplied function.

        Parameters
        ----------
        func : function
            Function by which ensemble members will be processed.
        **kwargs
            Keyword arguments passed to `func`.

        Returns
        -------
        :obj:`~isicle.conformers.ConformationalEnsemble` or list
            Result of operation, type depends on `func` return type.

        '''

        # Apply method to collection
        result = [func(x, **kwargs) for x in self]

        # Return ConformationalEnsemble if correct result type
        try:
            return ConformationalEnsemble(result)

        # Return result as-is
        except:
            return result

    # TODO: automatically unpack multiple returned objects
    def apply(self, func=None, method=None, **kwargs):
        '''
        Process conformational ensemble members according to supplied function
        or method.

        Parameters
        ----------
        func : function
            Function by which ensemble members will be processed.
        method : str
            Method by which ensemble members will be processed.
        **kwargs
            Keyword arguments passed to `method`.

        Returns
        -------
        :obj:`~isicle.conformers.ConformationalEnsemble` or list
            Result of operation, type depends on `method` return type.

        Raises
        ------
        ValueError
            If neither `func` nor `method` is supplied.

        '''
        if func is not None:
            return self._apply_function(func, **kwargs)

        if method is not None:
            return self._apply_method(method, **kwargs)

        raise ValueError('Must supply `func` or `method`.')

    def save_pickle(self, path):
        '''
        Pickle this class instance.

        Parameters
        ----------
        path : str
            Path to save pickle object to.

        '''

        with open(path, 'wb') as f:
            pickle.dump(self, f)

    def save(self, path):
        '''
        Save this class instance.

        Parameters
        ----------
        path : str
            Path to save object to.

        '''

        self.save_pickle(path)
