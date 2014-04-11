import numpy as np
from copy import deepcopy
from textwrap import dedent

from xray import Dataset, DataArray, XArray, align
from . import TestCase, ReturnItem


class TestDataArray(TestCase):
    def setUp(self):
        self.x = np.random.random((10, 20))
        self.v = XArray(['x', 'y'], self.x)
        self.ds = Dataset({'foo': self.v})
        self.dv = DataArray(self.ds, 'foo')

    def test_repr(self):
        v = XArray(['time', 'x'], [[1, 2, 3], [4, 5, 6]], {'foo': 'bar'})
        data_array = Dataset({'my_variable': v})['my_variable']
        expected = dedent("""
        <xray.DataArray 'my_variable' (time: 2, x: 3)>
        array([[1, 2, 3],
               [4, 5, 6]])
        Attributes:
            foo: bar
        """).strip()
        self.assertEqual(expected, repr(data_array))

    def test_properties(self):
        self.assertIs(self.dv.dataset, self.ds)
        self.assertEqual(self.dv.name, 'foo')
        self.assertXArrayEqual(self.dv.variable, self.v)
        self.assertArrayEqual(self.dv.data, self.v.data)
        for attr in ['dimensions', 'dtype', 'shape', 'size', 'ndim',
                     'attributes']:
            self.assertEqual(getattr(self.dv, attr), getattr(self.v, attr))
        self.assertEqual(len(self.dv), len(self.v))
        self.assertXArrayEqual(self.dv, self.v)
        self.assertEqual(list(self.dv.coordinates), list(self.ds.coordinates))
        for k, v in self.dv.coordinates.iteritems():
            self.assertArrayEqual(v, self.ds.coordinates[k])
        with self.assertRaises(AttributeError):
            self.dv.name = 'bar'
        with self.assertRaises(AttributeError):
            self.dv.dataset = self.ds

    def test_items(self):
        # strings pull out dataviews
        self.assertDataArrayEqual(self.dv, self.ds['foo'])
        x = self.dv['x']
        y = self.dv['y']
        self.assertDataArrayEqual(DataArray(self.ds, 'x'), x)
        self.assertDataArrayEqual(DataArray(self.ds, 'y'), y)
        # integer indexing
        I = ReturnItem()
        for i in [I[:], I[...], I[x.data], I[x.variable], I[x], I[x, y],
                  I[x.data > -1], I[x.variable > -1], I[x > -1],
                  I[x > -1, y > -1]]:
            self.assertXArrayEqual(self.dv, self.dv[i])
        for i in [I[0], I[:, 0], I[:3, :2],
                  I[x.data[:3]], I[x.variable[:3]], I[x[:3]], I[x[:3], y[:4]],
                  I[x.data > 3], I[x.variable > 3], I[x > 3], I[x > 3, y > 3]]:
            self.assertXArrayEqual(self.v[i], self.dv[i])
        # make sure we always keep the array around, even if it's a scalar
        self.assertXArrayEqual(self.dv[0, 0], self.dv.variable[0, 0])
        self.assertEqual(self.dv[0, 0].dataset,
                         Dataset({'foo': self.dv.variable[0, 0]}))

    def test_indexed_by(self):
        self.assertEqual(self.dv[0].dataset, self.ds.indexed_by(x=0))
        self.assertEqual(self.dv[:3, :5].dataset,
                         self.ds.indexed_by(x=slice(3), y=slice(5)))
        self.assertDataArrayEqual(self.dv, self.dv.indexed_by(x=slice(None)))
        self.assertDataArrayEqual(self.dv[:3], self.dv.indexed_by(x=slice(3)))

    def test_labeled_by(self):
        self.ds['x'] = ('x', np.array(list('abcdefghij')))
        self.assertDataArrayEqual(self.dv, self.dv.labeled_by(x=slice(None)))
        self.assertDataArrayEqual(self.dv[1], self.dv.labeled_by(x='b'))
        self.assertDataArrayEqual(self.dv[:3], self.dv.labeled_by(x=slice('c')))

    def test_loc(self):
        self.ds['x'] = ('x', np.array(list('abcdefghij')))
        self.assertDataArrayEqual(self.dv[:3], self.dv.loc[:'c'])
        self.assertDataArrayEqual(self.dv[1], self.dv.loc['b'])
        self.assertDataArrayEqual(self.dv[:3], self.dv.loc[['a', 'b', 'c']])
        self.assertDataArrayEqual(self.dv[:3, :4],
                             self.dv.loc[['a', 'b', 'c'], np.arange(4)])
        self.dv.loc['a':'j'] = 0
        self.assertTrue(np.all(self.dv.data == 0))

    def test_rename(self):
        renamed = self.dv.rename('bar')
        self.assertEqual(renamed.dataset, self.ds.rename({'foo': 'bar'}))
        self.assertEqual(renamed.name, 'bar')

        renamed = self.dv.rename({'foo': 'bar'})
        self.assertEqual(renamed.dataset, self.ds.rename({'foo': 'bar'}))
        self.assertEqual(renamed.name, 'bar')

    def test_dataset_getitem(self):
        dv = self.ds['foo']
        self.assertDataArrayEqual(dv, self.dv)

    def test_array_interface(self):
        self.assertArrayEqual(np.asarray(self.dv), self.x)
        # test patched in methods
        self.assertArrayEqual(self.dv.take([2, 3]), self.v.take([2, 3]))
        self.assertXArrayEqual(self.dv.argsort(), self.v.argsort())
        self.assertXArrayEqual(self.dv.clip(2, 3), self.v.clip(2, 3))
        # test ufuncs
        expected = deepcopy(self.ds)
        expected['foo'][:] = np.sin(self.x)
        self.assertDataArrayEquiv(expected['foo'], np.sin(self.dv))
        self.assertDataArrayEquiv(self.dv, np.maximum(self.v, self.dv))
        bar = XArray(['x', 'y'], np.zeros((10, 20)))
        self.assertDataArrayEquiv(self.dv, np.maximum(self.dv, bar))

    def test_math(self):
        x = self.x
        v = self.v
        a = self.dv
        # variable math was already tested extensively, so let's just make sure
        # that all types are properly converted here
        self.assertDataArrayEquiv(a, +a)
        self.assertDataArrayEquiv(a, a + 0)
        self.assertDataArrayEquiv(a, 0 + a)
        self.assertDataArrayEquiv(a, a + 0 * v)
        self.assertDataArrayEquiv(a, 0 * v + a)
        self.assertDataArrayEquiv(a, a + 0 * x)
        self.assertDataArrayEquiv(a, 0 * x + a)
        self.assertDataArrayEquiv(a, a + 0 * a)
        self.assertDataArrayEquiv(a, 0 * a + a)
        # test different indices
        ds2 = self.ds.update({'x': ('x', 3 + np.arange(10))}, inplace=False)
        b = DataArray(ds2, 'foo')
        with self.assertRaisesRegexp(ValueError, 'not aligned'):
            a + b
        with self.assertRaisesRegexp(ValueError, 'not aligned'):
            b + a

    def test_dataset_math(self):
        # verify that mathematical operators keep around the expected variables
        # when doing math with dataset arrays from one or more aligned datasets
        obs = Dataset({'tmin': ('x', np.arange(5)),
                       'tmax': ('x', 10 + np.arange(5)),
                       'x': ('x', 0.5 * np.arange(5))})

        actual = 2 * obs['tmax']
        expected = Dataset({'tmax2': ('x', 2 * (10 + np.arange(5))),
                            'x': obs['x']})['tmax2']
        self.assertDataArrayEquiv(actual, expected)

        actual = obs['tmax'] - obs['tmin']
        expected = Dataset({'trange': ('x', 10 * np.ones(5)),
                            'x': obs['x']})['trange']
        self.assertDataArrayEquiv(actual, expected)

        sim = Dataset({'tmin': ('x', 1 + np.arange(5)),
                       'tmax': ('x', 11 + np.arange(5)),
                       'x': ('x', 0.5 * np.arange(5))})

        actual = sim['tmin'] - obs['tmin']
        expected = Dataset({'error': ('x', np.ones(5)),
                            'x': obs['x']})['error']
        self.assertDataArrayEquiv(actual, expected)

        # in place math shouldn't remove or conflict with other variables
        actual = deepcopy(sim['tmin'])
        actual -= obs['tmin']
        expected = Dataset({'tmin': ('x', np.ones(5)),
                            'tmax': sim['tmax'],
                            'x': sim['x']})['tmin']
        self.assertDataArrayEquiv(actual, expected)

    def test_coord_math(self):
        ds = Dataset({'x': ('x', 1 + np.arange(3))})
        expected = ds.copy()
        expected['x2'] = ('x', np.arange(3))
        actual = ds['x'] - 1
        self.assertDataArrayEquiv(expected['x2'], actual)

    def test_item_math(self):
        self.ds['x'] = ('x', np.array(list('abcdefghij')))
        self.assertXArrayEqual(self.dv + self.dv[0, 0],
                               self.dv + self.dv[0, 0].data)
        new_data = self.x[0][None, :] + self.x[:, 0][:, None]
        self.assertXArrayEqual(self.dv[:, 0] + self.dv[0],
                               XArray(['x', 'y'], new_data))
        self.assertXArrayEqual(self.dv[0] + self.dv[:, 0],
                               XArray(['y', 'x'], new_data.T))

    def test_inplace_math(self):
        x = self.x
        v = self.v
        a = self.dv
        b = a
        b += 1
        self.assertIs(b, a)
        self.assertIs(b.variable, v)
        self.assertIs(b.data, x)
        self.assertIs(b.dataset, self.ds)

    def test_transpose(self):
        self.assertXArrayEqual(self.dv.variable.transpose(),
                               self.dv.transpose())

    def test_squeeze(self):
        self.assertXArrayEqual(self.dv.variable.squeeze(), self.dv.squeeze())

    def test_reduce(self):
        self.assertXArrayEqual(self.dv.reduce(np.mean, 'x'),
                            self.v.reduce(np.mean, 'x'))
        # needs more...
        # should check which extra dimensions are dropped

    def test_groupby_iter(self):
        for ((act_x, act_dv), (exp_x, exp_ds)) in \
                zip(self.dv.groupby('y'), self.ds.groupby('y')):
            self.assertEqual(exp_x, act_x)
            self.assertDataArrayEqual(DataArray(exp_ds, 'foo'), act_dv)
        for ((_, exp_dv), act_dv) in zip(self.dv.groupby('x'), self.dv):
            self.assertDataArrayEqual(exp_dv, act_dv)

    def test_groupby(self):
        agg_var = XArray(['y'], np.array(['a'] * 9 + ['c'] + ['b'] * 10))
        self.dv['abc'] = agg_var
        self.dv['y'] = 20 + 100 * self.ds['y'].variable

        identity = lambda x: x
        for g in ['x', 'y', 'abc']:
            for shortcut in [False, True]:
                for squeeze in [False, True]:
                    expected = self.dv
                    grouped = self.dv.groupby(g, squeeze=squeeze)
                    actual = grouped.apply(identity, shortcut=shortcut)
                    self.assertDataArrayEqual(expected, actual)

        grouped = self.dv.groupby('abc', squeeze=True)
        expected_sum_all = DataArray(Dataset(
            {'foo': XArray(['abc'], np.array([self.x[:, :9].sum(),
                                              self.x[:, 10:].sum(),
                                              self.x[:, 9:10].sum()]).T,
                           {'cell_methods': 'x: y: sum'}),
             'abc': XArray(['abc'], np.array(['a', 'b', 'c']))}), 'foo')
        self.assertDataArrayAllClose(
            expected_sum_all, grouped.reduce(np.sum, dimension=None))
        self.assertDataArrayAllClose(
            expected_sum_all, grouped.sum(dimension=None))
        self.assertDataArrayAllClose(
            expected_sum_all, grouped.sum(axis=None))
        expected_unique = XArray('abc', ['a', 'b', 'c'])
        self.assertXArrayEqual(expected_unique, grouped.unique_coord)
        self.assertEqual(3, len(grouped))

        grouped = self.dv.groupby('abc', squeeze=False)
        self.assertDataArrayAllClose(
            expected_sum_all, grouped.sum(dimension=None))

        expected_sum_axis1 = DataArray(Dataset(
            {'foo': XArray(['x', 'abc'], np.array([self.x[:, :9].sum(1),
                                                   self.x[:, 10:].sum(1),
                                                   self.x[:, 9:10].sum(1)]).T,
                           {'cell_methods': 'y: sum'}),
             'x': self.ds.variables['x'],
             'abc': XArray(['abc'], np.array(['a', 'b', 'c']))}), 'foo')
        self.assertDataArrayAllClose(expected_sum_axis1, grouped.reduce(np.sum))
        self.assertDataArrayAllClose(expected_sum_axis1, grouped.sum())
        self.assertDataArrayAllClose(expected_sum_axis1, grouped.sum('y'))

    def test_concat(self):
        self.ds['bar'] = XArray(['x', 'y'], np.random.randn(10, 20))
        foo = self.ds['foo'].select()
        bar = self.ds['bar'].rename('foo').select()
        # from dataset array:
        self.assertXArrayEqual(XArray(['w', 'x', 'y'],
                                      np.array([foo.data, bar.data])),
                               DataArray.concat([foo, bar], 'w'))
        # from iteration:
        grouped = [g for _, g in foo.groupby('x')]
        stacked = DataArray.concat(grouped, self.ds['x'])
        self.assertDataArrayEqual(foo.select(), stacked)

    def test_align(self):
        self.ds['x'] = ('x', np.array(list('abcdefghij')))
        with self.assertRaises(ValueError):
            self.dv + self.dv[:5]
        dv1, dv2 = align(self.dv, self.dv[:5], join='inner')
        self.assertDataArrayEqual(dv1, self.dv[:5])
        self.assertDataArrayEqual(dv2, self.dv[:5])

    def test_to_and_from_series(self):
        expected = self.dv.to_dataframe()['foo']
        actual = self.dv.to_series()
        self.assertArrayEqual(expected.values, actual.values)
        self.assertArrayEqual(expected.index.values, actual.index.values)
        self.assertEqual('foo', actual.name)
        # test roundtrip
        self.assertDataArrayEqual(self.dv, DataArray.from_series(actual))