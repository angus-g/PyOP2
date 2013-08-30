# This file is part of PyOP2
#
# PyOP2 is Copyright (c) 2012, Imperial College London and
# others. Please see the AUTHORS file in the main source directory for
# a full list of copyright holders.  All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * The name of Imperial College London or that of other
#       contributors may not be used to endorse or promote products
#       derived from this software without specific prior written
#       permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTERS
# ''AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT HOLDERS OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
# OF THE POSSIBILITY OF SUCH DAMAGE.

import pytest
import numpy
import random
from pyop2 import plan
from pyop2 import op2


def _seed():
    return 0.02041724

nelems = 8


@pytest.fixture
def iterset():
    return op2.Set(nelems, "iterset")


@pytest.fixture
def indset():
    return op2.Set(nelems, "indset")


@pytest.fixture
def diterset(iterset):
    return op2.DataSet(iterset, 1, "diterset")


@pytest.fixture
def dindset(indset):
    return op2.DataSet(indset, 1, "dindset")


@pytest.fixture
def dindset2(indset):
    return op2.DataSet(indset, 2, "dindset2")


@pytest.fixture
def g():
    return op2.Global(1, 0, numpy.uint32, "g")


@pytest.fixture
def x(dindset):
    return op2.Dat(dindset, range(nelems), numpy.uint32, "x")


@pytest.fixture
def x2(dindset2):
    return op2.Dat(dindset2, range(nelems) * 2, numpy.uint32, "x2")


@pytest.fixture
def xl(dindset):
    return op2.Dat(dindset, range(nelems), numpy.uint64, "xl")


@pytest.fixture
def y(dindset):
    return op2.Dat(dindset, [0] * nelems, numpy.uint32, "y")


@pytest.fixture
def iter2ind1(iterset, indset):
    u_map = numpy.array(range(nelems), dtype=numpy.uint32)
    random.shuffle(u_map, _seed)
    return op2.Map(iterset, indset, 1, u_map, "iter2ind1")


@pytest.fixture
def iter2ind2(iterset, indset):
    u_map = numpy.array(range(nelems) * 2, dtype=numpy.uint32)
    random.shuffle(u_map, _seed)
    return op2.Map(iterset, indset, 2, u_map, "iter2ind2")


class TestPlanCache:

    """
    Plan Object Cache Tests.
    """
    # No plan for sequential backend
    skip_backends = ['sequential']
    cache = plan.Plan._cache

    @pytest.fixture
    def mat(cls, iter2ind1, dindset):
        sparsity = op2.Sparsity((dindset, dindset), (iter2ind1, iter2ind1), "sparsity")
        return op2.Mat(sparsity, 'float64', "mat")

    @pytest.fixture
    def a64(cls, iterset, diterset):
        return op2.Dat(diterset, range(nelems), numpy.uint64, "a")

    def test_plan_per_iterset_partition(self, backend):
        set = op2.Set([2, 4, 4, 4], "set")
        indset = op2.Set(4, "indset")
        dat = op2.Dat(set ** 1, [0, 1, 2, 3], dtype=numpy.int32)
        inddat = op2.Dat(indset ** 1, [0, 0, 0, 0], dtype=numpy.int32)
        map = op2.Map(set, indset, 1, [0, 1, 2, 3])

        self.cache.clear()
        assert len(self.cache) == 0

        op2.par_loop(op2.Kernel("void assign(int* src, int* dst) { *dst = *src; }",
                                "assign"),
                     set,
                     dat(op2.READ),
                     inddat(op2.WRITE, map[0]))
        assert (dat.data == inddat.data).all()
        assert len(self.cache) == 2

    def test_same_arg(self, backend, iterset, iter2ind1, x):
        self.cache.clear()
        assert len(self.cache) == 0

        kernel_inc = "void kernel_inc(unsigned int* x) { *x += 1; }"
        kernel_dec = "void kernel_dec(unsigned int* x) { *x -= 1; }"

        op2.par_loop(op2.Kernel(kernel_inc, "kernel_inc"),
                     iterset,
                     x(op2.RW, iter2ind1[0]))
        op2.base._trace.evaluate(set([x]), set())
        assert len(self.cache) == 1

        op2.par_loop(op2.Kernel(kernel_dec, "kernel_dec"),
                     iterset,
                     x(op2.RW, iter2ind1[0]))
        op2.base._trace.evaluate(set([x]), set())
        assert len(self.cache) == 1

    def test_arg_order(self, backend, iterset, iter2ind1, x, y):
        self.cache.clear()
        assert len(self.cache) == 0

        kernel_swap = """
void kernel_swap(unsigned int* x, unsigned int* y)
{
  unsigned int t;
  t = *x;
  *x = *y;
  *y = t;
}
"""
        op2.par_loop(op2.Kernel(kernel_swap, "kernel_swap"),
                     iterset,
                     x(op2.RW, iter2ind1[0]),
                     y(op2.RW, iter2ind1[0]))

        op2.base._trace.evaluate(set([x]), set())
        assert len(self.cache) == 1

        op2.par_loop(op2.Kernel(kernel_swap, "kernel_swap"),
                     iterset,
                     y(op2.RW, iter2ind1[0]),
                     x(op2.RW, iter2ind1[0]))

        op2.base._trace.evaluate(set([x]), set())
        assert len(self.cache) == 1

    def test_idx_order(self, backend, iterset, iter2ind2, x):
        self.cache.clear()
        assert len(self.cache) == 0

        kernel_swap = """
void kernel_swap(unsigned int* x, unsigned int* y)
{
  unsigned int t;
  t = *x;
  *x = *y;
  *y = t;
}
"""
        op2.par_loop(op2.Kernel(kernel_swap, "kernel_swap"),
                     iterset,
                     x(op2.RW, iter2ind2[0]),
                     x(op2.RW, iter2ind2[1]))

        op2.base._trace.evaluate(set([x]), set())
        assert len(self.cache) == 1

        op2.par_loop(op2.Kernel(kernel_swap, "kernel_swap"),
                     iterset,
                     x(op2.RW, iter2ind2[1]),
                     x(op2.RW, iter2ind2[0]))

        op2.base._trace.evaluate(set([x]), set())
        assert len(self.cache) == 1

    def test_dat_same_size_times_dim(self, backend, iterset, iter2ind1, iter2ind2, x2, xl):
        self.cache.clear()
        assert len(self.cache) == 0

        kernel_swap = """
void kernel_swap(unsigned int* x)
{
  unsigned int t;
  t = *x;
  *x = *(x+1);
  *(x+1) = t;
}
"""
        op2.par_loop(op2.Kernel(kernel_swap, "kernel_swap"),
                     iterset,
                     x2(op2.RW, iter2ind2[0]))

        op2.base._trace.evaluate(set([x2]), set())
        assert len(self.cache) == 1

        kernel_inc = "void kernel_inc(unsigned long* x) { *x += 1; }"
        op2.par_loop(op2.Kernel(kernel_inc, "kernel_inc"),
                     iterset,
                     xl(op2.RW, iter2ind1[0]))

        op2.base._trace.evaluate(set([xl]), set())
        assert len(self.cache) == 2

    def test_same_nonstaged_arg_count(self, backend, iterset, iter2ind1, x, a64, g):
        self.cache.clear()
        assert len(self.cache) == 0

        kernel_dummy = "void kernel_dummy(unsigned int* x, unsigned long* a64) { }"
        op2.par_loop(op2.Kernel(kernel_dummy, "kernel_dummy"),
                     iterset,
                     x(op2.INC, iter2ind1[0]),
                     a64(op2.RW))
        op2.base._trace.evaluate(set([x]), set())
        assert len(self.cache) == 1

        kernel_dummy = "void kernel_dummy(unsigned int* x, unsigned int* g) { }"
        op2.par_loop(op2.Kernel(kernel_dummy, "kernel_dummy"),
                     iterset,
                     x(op2.INC, iter2ind1[0]),
                     g(op2.READ))
        op2.base._trace.evaluate(set([x]), set())
        assert len(self.cache) == 1

    def test_same_conflicts(self, backend, iterset, iter2ind2, x, y):
        self.cache.clear()
        assert len(self.cache) == 0

        kernel_dummy = "void kernel_dummy(unsigned int* x, unsigned int* y) { }"
        op2.par_loop(op2.Kernel(kernel_dummy, "kernel_dummy"),
                     iterset,
                     x(op2.INC, iter2ind2[0]),
                     x(op2.INC, iter2ind2[1]))
        op2.base._trace.evaluate(set([x]), set())
        assert len(self.cache) == 1

        kernel_dummy = "void kernel_dummy(unsigned int* x, unsigned int* y) { }"
        op2.par_loop(op2.Kernel(kernel_dummy, "kernel_dummy"),
                     iterset,
                     y(op2.INC, iter2ind2[0]),
                     y(op2.INC, iter2ind2[1]))
        op2.base._trace.evaluate(set([y]), set())
        assert len(self.cache) == 1

    def test_diff_conflicts(self, backend, iterset, iter2ind2, x, y):
        self.cache.clear()
        assert len(self.cache) == 0

        kernel_dummy = "void kernel_dummy(unsigned int* x, unsigned int* y) { }"
        op2.par_loop(op2.Kernel(kernel_dummy, "kernel_dummy"),
                     iterset,
                     x(op2.READ, iter2ind2[0]),
                     x(op2.READ, iter2ind2[1],))
        op2.base._trace.evaluate(set(), set([x]))
        assert len(self.cache) == 1

        kernel_dummy = "void kernel_dummy(unsigned int* x, unsigned int* y) { }"
        op2.par_loop(op2.Kernel(kernel_dummy, "kernel_dummy"),
                     iterset,
                     y(op2.INC, iter2ind2[0]),
                     y(op2.INC, iter2ind2[1]))
        op2.base._trace.evaluate(set([y]), set())
        assert len(self.cache) == 2

    def test_same_with_mat(self, backend, iterset, x, iter2ind1, mat):
        self.cache.clear()
        assert len(self.cache) == 0
        plan1 = plan.Plan(iterset.all_part,
                          mat(op2.INC, (iter2ind1[op2.i[0]],
                                        iter2ind1[op2.i[1]])),
                          x(op2.READ, iter2ind1[0]),
                          partition_size=10,
                          matrix_coloring=True)

        op2.base._trace.evaluate(set([mat]), set())
        assert len(self.cache) == 1
        plan2 = plan.Plan(iterset.all_part,
                          mat(op2.INC, (iter2ind1[op2.i[0]],
                                        iter2ind1[op2.i[1]])),
                          x(op2.READ, iter2ind1[0]),
                          partition_size=10,
                          matrix_coloring=True)

        op2.base._trace.evaluate(set([mat]), set())
        assert len(self.cache) == 1
        assert plan1 is plan2

    def test_iteration_index_order_matters_with_mat(self, backend, iterset,
                                                    x, iter2ind1, mat):
        self.cache.clear()
        assert len(self.cache) == 0
        plan1 = plan.Plan(iterset.all_part,
                          mat(op2.INC, (iter2ind1[op2.i[0]],
                                        iter2ind1[op2.i[1]])),
                          x(op2.READ, iter2ind1[0]),
                          partition_size=10,
                          matrix_coloring=True)

        op2.base._trace.evaluate(set([mat]), set())
        assert len(self.cache) == 1
        plan2 = plan.Plan(iterset.all_part,
                          mat(op2.INC, (iter2ind1[op2.i[1]],
                                        iter2ind1[op2.i[0]])),
                          x(op2.READ, iter2ind1[0]),
                          partition_size=10,
                          matrix_coloring=True)

        op2.base._trace.evaluate(set([mat]), set())
        assert len(self.cache) == 2
        assert plan1 is not plan2


class TestGeneratedCodeCache:

    """
    Generated Code Cache Tests.
    """

    cache = op2.base.JITModule._cache

    @pytest.fixture
    def a(cls, diterset):
        return op2.Dat(diterset, range(nelems), numpy.uint32, "a")

    @pytest.fixture
    def b(cls, diterset):
        return op2.Dat(diterset, range(nelems), numpy.uint32, "b")

    def test_same_args(self, backend, iterset, iter2ind1, x, a):
        self.cache.clear()
        assert len(self.cache) == 0

        kernel_cpy = "void kernel_cpy(unsigned int* dst, unsigned int* src) { *dst = *src; }"

        op2.par_loop(op2.Kernel(kernel_cpy, "kernel_cpy"),
                     iterset,
                     a(op2.WRITE),
                     x(op2.READ, iter2ind1[0]))

        op2.base._trace.evaluate(set([a]), set())
        assert len(self.cache) == 1

        op2.par_loop(op2.Kernel(kernel_cpy, "kernel_cpy"),
                     iterset,
                     a(op2.WRITE),
                     x(op2.READ, iter2ind1[0]))

        op2.base._trace.evaluate(set([a]), set())
        assert len(self.cache) == 1

    def test_diff_kernel(self, backend, iterset, iter2ind1, x, a):
        self.cache.clear()
        assert len(self.cache) == 0

        kernel_cpy = "void kernel_cpy(unsigned int* dst, unsigned int* src) { *dst = *src; }"

        op2.par_loop(op2.Kernel(kernel_cpy, "kernel_cpy"),
                     iterset,
                     a(op2.WRITE),
                     x(op2.READ, iter2ind1[0]))

        op2.base._trace.evaluate(set([a]), set())
        assert len(self.cache) == 1

        kernel_cpy = "void kernel_cpy(unsigned int* DST, unsigned int* SRC) { *DST = *SRC; }"

        op2.par_loop(op2.Kernel(kernel_cpy, "kernel_cpy"),
                     iterset,
                     a(op2.WRITE),
                     x(op2.READ, iter2ind1[0]))

        op2.base._trace.evaluate(set([a]), set())
        assert len(self.cache) == 2

    def test_invert_arg_similar_shape(self, backend, iterset, iter2ind1, x, y):
        self.cache.clear()
        assert len(self.cache) == 0

        kernel_swap = """
void kernel_swap(unsigned int* x, unsigned int* y)
{
  unsigned int t;
  t = *x;
  *x = *y;
  *y = t;
}
"""
        op2.par_loop(op2.Kernel(kernel_swap, "kernel_swap"),
                     iterset,
                     x(op2.RW, iter2ind1[0]),
                     y(op2.RW, iter2ind1[0]))

        op2.base._trace.evaluate(set([x]), set())
        assert len(self.cache) == 1

        op2.par_loop(op2.Kernel(kernel_swap, "kernel_swap"),
                     iterset,
                     y(op2.RW, iter2ind1[0]),
                     x(op2.RW, iter2ind1[0]))

        op2.base._trace.evaluate(set([y]), set())
        assert len(self.cache) == 1

    def test_dloop_ignore_scalar(self, backend, iterset, a, b):
        self.cache.clear()
        assert len(self.cache) == 0

        kernel_swap = """
void kernel_swap(unsigned int* x, unsigned int* y)
{
  unsigned int t;
  t = *x;
  *x = *y;
  *y = t;
}
"""
        op2.par_loop(op2.Kernel(kernel_swap, "kernel_swap"),
                     iterset,
                     a(op2.RW),
                     b(op2.RW))

        op2.base._trace.evaluate(set([a]), set())
        assert len(self.cache) == 1

        op2.par_loop(op2.Kernel(kernel_swap, "kernel_swap"),
                     iterset,
                     b(op2.RW),
                     a(op2.RW))

        op2.base._trace.evaluate(set([b]), set())
        assert len(self.cache) == 1

    def test_vector_map(self, backend, iterset, x2, iter2ind2):
        self.cache.clear()
        assert len(self.cache) == 0

        kernel_swap = """
void kernel_swap(unsigned int* x[2])
{
  unsigned int t;
  t = x[0][0];
  x[0][0] = x[0][1];
  x[0][1] = t;
}
"""

        op2.par_loop(op2.Kernel(kernel_swap, "kernel_swap"),
                     iterset,
                     x2(op2.RW, iter2ind2))

        op2.base._trace.evaluate(set([x2]), set())
        assert len(self.cache) == 1

        op2.par_loop(op2.Kernel(kernel_swap, "kernel_swap"),
                     iterset,
                     x2(op2.RW, iter2ind2))

        op2.base._trace.evaluate(set([x2]), set())
        assert len(self.cache) == 1

    def test_map_index_order_matters(self, backend, iterset, x2, iter2ind2):
        self.cache.clear()
        assert len(self.cache) == 0
        k = op2.Kernel("""void k(unsigned int *x, unsigned int *y) {}""", 'k')

        op2.par_loop(k, iterset,
                     x2(op2.INC, iter2ind2[0]),
                     x2(op2.INC, iter2ind2[1]))

        op2.base._trace.evaluate(set([x2]), set())
        assert len(self.cache) == 1

        op2.par_loop(k, iterset,
                     x2(op2.INC, iter2ind2[1]),
                     x2(op2.INC, iter2ind2[0]))

        op2.base._trace.evaluate(set([x2]), set())
        assert len(self.cache) == 2

    def test_same_iteration_space_works(self, backend, iterset, x2, iter2ind2):
        self.cache.clear()
        assert len(self.cache) == 0
        k = op2.Kernel("""void k(unsigned int *x, int i) {}""", 'k')

        op2.par_loop(k, iterset,
                     x2(op2.INC, iter2ind2[op2.i[0]]))

        op2.base._trace.evaluate(set([x2]), set())
        assert len(self.cache) == 1

        op2.par_loop(k, iterset,
                     x2(op2.INC, iter2ind2[op2.i[0]]))

        op2.base._trace.evaluate(set([x2]), set())
        assert len(self.cache) == 1

    def test_change_const_dim_matters(self, backend, iterset, diterset):
        d = op2.Dat(diterset, range(nelems), numpy.uint32)
        self.cache.clear()
        assert len(self.cache) == 0

        k = op2.Kernel("""void k(unsigned int *x) {}""", 'k')
        c = op2.Const(1, 1, name='c', dtype=numpy.uint32)

        op2.par_loop(k, iterset, d(op2.WRITE))

        op2.base._trace.evaluate(set([d]), set())
        assert len(self.cache) == 1

        c.remove_from_namespace()

        c = op2.Const(2, (1, 1), name='c', dtype=numpy.uint32)

        op2.par_loop(k, iterset, d(op2.WRITE))

        op2.base._trace.evaluate(set([d]), set())
        assert len(self.cache) == 2

        c.remove_from_namespace()

    def test_change_const_data_doesnt_matter(self, backend, iterset, diterset):
        d = op2.Dat(diterset, range(nelems), numpy.uint32)
        self.cache.clear()
        assert len(self.cache) == 0

        k = op2.Kernel("""void k(unsigned int *x) {}""", 'k')
        c = op2.Const(1, 1, name='c', dtype=numpy.uint32)

        op2.par_loop(k, iterset, d(op2.WRITE))

        op2.base._trace.evaluate(set([d]), set())
        assert len(self.cache) == 1

        c.data = 2
        op2.par_loop(k, iterset, d(op2.WRITE))

        op2.base._trace.evaluate(set([d]), set())
        assert len(self.cache) == 1

        c.remove_from_namespace()

    def test_change_dat_dtype_matters(self, backend, iterset, diterset):
        d = op2.Dat(diterset, range(nelems), numpy.uint32)
        self.cache.clear()
        assert len(self.cache) == 0

        k = op2.Kernel("""void k(void *x) {}""", 'k')

        op2.par_loop(k, iterset, d(op2.WRITE))

        op2.base._trace.evaluate(set([d]), set())
        assert len(self.cache) == 1

        d = op2.Dat(diterset, range(nelems), numpy.int32)
        op2.par_loop(k, iterset, d(op2.WRITE))

        op2.base._trace.evaluate(set([d]), set())
        assert len(self.cache) == 2

    def test_change_global_dtype_matters(self, backend, iterset, diterset):
        g = op2.Global(1, 0, dtype=numpy.uint32)
        self.cache.clear()
        assert len(self.cache) == 0

        k = op2.Kernel("""void k(void *x) {}""", 'k')

        op2.par_loop(k, iterset, g(op2.INC))

        op2.base._trace.evaluate(set([g]), set())
        assert len(self.cache) == 1

        g = op2.Global(1, 0, dtype=numpy.float64)
        op2.par_loop(k, iterset, g(op2.INC))

        op2.base._trace.evaluate(set([g]), set())
        assert len(self.cache) == 2


class TestKernelCache:

    """
    Kernel caching tests.
    """

    cache = op2.base.Kernel._cache

    def test_kernels_same_code_same_name(self, backend):
        """Kernels with same code and name should be retrieved from cache."""
        code = "void k(void *x) {}"
        self.cache.clear()
        k1 = op2.Kernel(code, 'k')
        k2 = op2.Kernel(code, 'k')
        assert k1 is k2 and len(self.cache) == 1

    def test_kernels_same_code_differing_name(self, backend):
        """Kernels with same code and different name should not be retrieved
        from cache."""
        self.cache.clear()
        code = "void k(void *x) {}"
        k1 = op2.Kernel(code, 'k')
        k2 = op2.Kernel(code, 'l')
        assert k1 is not k2 and len(self.cache) == 2

    def test_kernels_differing_code_same_name(self, backend):
        """Kernels with different code and same name should not be retrieved
        from cache."""
        self.cache.clear()
        k1 = op2.Kernel("void k(void *x) {}", 'k')
        k2 = op2.Kernel("void l(void *x) {}", 'k')
        assert k1 is not k2 and len(self.cache) == 2

    def test_kernels_differing_code_differing_name(self, backend):
        """Kernels with different code and different name should not be
        retrieved from cache."""
        self.cache.clear()
        k1 = op2.Kernel("void k(void *x) {}", 'k')
        k2 = op2.Kernel("void l(void *x) {}", 'l')
        assert k1 is not k2 and len(self.cache) == 2


class TestSparsityCache:

    @pytest.fixture
    def s1(cls):
        return op2.Set(5)

    @pytest.fixture
    def s2(cls):
        return op2.Set(5)

    @pytest.fixture
    def ds2(cls, s2):
        return op2.DataSet(s2, 1)

    @pytest.fixture
    def m1(cls, s1, s2):
        return op2.Map(s1, s2, 1, [0, 1, 2, 3, 4])

    @pytest.fixture
    def m2(cls, s1, s2):
        return op2.Map(s1, s2, 1, [1, 2, 3, 4, 0])

    def test_sparsities_differing_maps_not_cached(self, backend, m1, m2, ds2):
        """Sparsities with different maps should not share a C handle."""
        sp1 = op2.Sparsity(ds2, m1)
        sp2 = op2.Sparsity(ds2, m2)
        assert sp1 is not sp2

    def test_sparsities_differing_map_pairs_not_cached(self, backend, m1, m2, ds2):
        """Sparsities with different maps should not share a C handle."""
        sp1 = op2.Sparsity((ds2, ds2), (m1, m2))
        sp2 = op2.Sparsity((ds2, ds2), (m2, m1))
        assert sp1 is not sp2

    def test_sparsities_differing_map_tuples_not_cached(self, backend, m1, m2, ds2):
        """Sparsities with different maps should not share a C handle."""
        sp1 = op2.Sparsity((ds2, ds2), ((m1, m1), (m2, m2)))
        sp2 = op2.Sparsity((ds2, ds2), ((m2, m2), (m2, m2)))
        assert sp1 is not sp2

    def test_sparsities_same_map_cached(self, backend, m1, ds2):
        """Sparsities with the same map should share a C handle."""
        sp1 = op2.Sparsity(ds2, m1)
        sp2 = op2.Sparsity(ds2, m1)
        assert sp1 is sp2

    def test_sparsities_same_map_pair_cached(self, backend, m1, ds2):
        """Sparsities with the same map pair should share a C handle."""
        sp1 = op2.Sparsity((ds2, ds2), (m1, m1))
        sp2 = op2.Sparsity((ds2, ds2), (m1, m1))
        assert sp1 is sp2

    def test_sparsities_same_map_tuple_cached(self, backend, m1, m2, ds2):
        "Sparsities with the same tuple of map pairs should share a C handle."
        sp1 = op2.Sparsity((ds2, ds2), ((m1, m1), (m2, m2)))
        sp2 = op2.Sparsity((ds2, ds2), ((m1, m1), (m2, m2)))
        assert sp1 is sp2

    def test_sparsities_different_ordered_map_tuple_cached(self, backend, m1, m2, ds2):
        "Sparsities with the same tuple of map pairs should share a C handle."
        sp1 = op2.Sparsity((ds2, ds2), ((m1, m1), (m2, m2)))
        sp2 = op2.Sparsity((ds2, ds2), ((m2, m2), (m1, m1)))
        assert sp1 is sp2

    def test_two_mats_on_same_sparsity_share_data(self, backend, m1, skip_sequential, skip_openmp, ds2):
        """Sparsity data should be shared between Mat objects.
        Even on the device."""
        sp = op2.Sparsity((ds2, ds2), (m1, m1))
        mat1 = op2.Mat(sp, 'float64')
        mat2 = op2.Mat(sp, 'float64')

        assert mat1._colidx is mat2._colidx
        assert mat1._rowptr is mat2._rowptr

if __name__ == '__main__':
    import os
    pytest.main(os.path.abspath(__file__))
