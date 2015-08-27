__author__ = 'jan-hendrikprinz'

import itertools
import collections

class TreeSetMixin(object):
    """
    A mixin that provides basic handling for sets of trees.

    A tree is basically a node with children of the same type. The mixin
    requires to implement `.subnodes` to contain a list of children.

    The `__contains__` operator requires `_default_match` to be implemented.
    Otherwise is defaults to a comparison between two elements.

    A tree set means that it actually does not represent a single tree but a whole
    group of trees. The description works by assuming that all leaves are actually
    different choices of a single leave.

    The main difficulty is that now leaves can have two meaning and we need to
    """

    NODE_TYPE_NONE = 0
    NODE_TYPE_ALL = 1
    NODE_TYPE_ONE = 2
    NODE_TYPE_ACCUMULATE = 3
    NODE_TYPE_POWER = 4
    NODE_TYPE_CUSTOM = 5

    @staticmethod
    def _indent(s):
        """
        Helper function to print indented subtrees

        Parameters
        ----------
        s : str
            string representation of a tree to be indented

        Returns
        -------
        str
            the indented representation
        """
        spl = s.split('\n')
        last = [ no for no, line in enumerate(spl) if len(line) > 0 and line[0] != ' ']
        if len(last) > 0:
            last = last[-1]
        else:
            last = len(spl)
        spl = [(' |  ' + p if no <= last else '    ' + p) if p[0] == ' ' else ' +- ' + p for no, p in enumerate(spl) if len(p)]
        return '\n'.join(spl)

    @property
    def _subnodes(self):
        return []

    def __iter__(self):
        """
        Traverse the whole tree in pre-order

        Returns
        -------
        Iterator
            an iterator that traverses the tree in pre-order
        """
        yield self
        for subchange in self._subnodes:
            for change in subchange:
                yield change

    def __getitem__(self, item):
        """
        Return the n-th subchange

        Returns
        -------
        PathMoveChange
            the n-th subchange if this PathMoveChange uses underlying changes
        """

        if type(item) is int:
            if item == 0:
                return self
            elif item > 0:
                return self._subnodes[item - 1]
            elif item < 0:
                return self._subnodes[item]


        if isinstance(item, tuple):
            self._last_found = None
            def match_find(original, test):
                self._last_found = original
                return self._default_match(original, test)

            find_match = TreeSetMixin._check_tree(
                self, item, match_find
            )

            if find_match:
                return self._last_found
            else:
                raise KeyError('Key %s not found in tree' % item)

        if type(item) is list:
            # this is assumed to be a tree
            if self._default_match(item[0], self):
                if len(item) > 1:
                    for ch in self._subnodes:
                        r = ch[item[1]]
                        if r is not None:
                            return r
                    return None
                else:
                    return self
            else:
                return None


    def __reversed__(self):
        """
        Traverse the whole tree in post-order

        Returns
        -------
        Iterator
            an iterator that traverses the tree in post-order
        """
        for subchange in self._subnodes:
            for change in reversed(subchange):
                yield change

        yield self

    def __len__(self):
        """
        Returns the total number of Changes mad in a move.

        Returns
        -------
        int
            the number of (Sub)PathMoveChanges in this PathMoveChange

        """
        if self._len is None:
            self._len = len(list(iter(self)))

        return self._len

    def key(self, change):
        tree = self.keylist()
        return [leave for leave in tree if leave[1] is change ][0][0]

    def locators(self):
        return self.keylist()

    def locate(self, item):
        return [key for key, value in self.keylist().iteritems() if value is item]

    @property
    def is_sequential(self):
        return len(self._leaves) < 2

    @property
    def deterministic(self):
        if not hasattr(self, '_deterministic'):
            if not self.is_sequential:
                self._deterministic = False
            else:
                self._deterministic = True
                for node in self._subnodes:
                    if not node.deterministic:
                        self._deterministic = False

        return self._deterministic


    @property
    def unique(self):
        ret = []
        if len(self._subnodes) == 0:
            ret = [self.identifier]
        elif self.deterministic:
            ret = [self.identifier]
        elif len(self._subnodes) == 1:
            ret = [self.identifier, self._subnodes[0].unique]
        else:
            ret = [self.identifier]
            if self.is_sequential:
                for sub in self._subnodes:
                    ret.append(sub.unique)
            else:
                for sub in self._subnodes:
                    ret.append(sub.unique)

        return tuple(ret)

    @property
    def enum(self):
        l = []
        ret = (self.identifier, )
        if self.deterministic:
            l.append(ret)
        else:
            for leave in self._leaves:
                if len(leave) == 0:
                    l.append(ret)
                else:
                    l.extend(itertools.product(ret, *map(lambda x : x.enum, leave)))

        return l

    @property
    def _leaves(self):
        if self._node_type == self.NODE_TYPE_ALL:
            return [[sub for sub in self._subnodes]]
        elif self._node_type == self.NODE_TYPE_ACCUMULATE:
            return [self._subnodes[:n+1] for n in range(0, len(self._subnodes))]
        elif self._node_type == self.NODE_TYPE_ONE:
            leaves = [[sub] for sub in self._subnodes]

            unique_leaves = list(set([ tuple(l) for l in leaves ]))

            return unique_leaves
        elif self._node_type == self.NODE_TYPE_POWER:
            s = list(self._subnodes)
            return itertools.chain.from_iterable(
                itertools.combinations(s, r) for r in range(len(s)+1)
            )
        elif self._node_type == self.NODE_TYPE_NONE:
            return []
        elif hasattr(self._node_type, '__call__'):
            return self._node_type()
        else:
            raise RuntimeError('Node has no type !')


    @classmethod
    def _check_tree(cls, tree, branch, match, leave_n = 0, start = 0, branch_n = 0):
        return TreeSetMixin._general_check_tree(tree, branch, match, lambda x : x._leaves, leave_n, start, branch_n)

    @classmethod
    def _general_check_tree(cls, tree, branch, match, leave_fnc, leave_n = 0, start = 0, branch_n = 0):
        WILDCARDS = {
            '*' : lambda s : slice(0,None),
            '.' : lambda s : slice(1,2),
            '?' : lambda s : slice(0,2),
            ':' : lambda s : slice(*map(int, s.split(':'))),
            None: lambda s : slice(1,2)
        }
        MATCH_ONE = ['.', '?', '*']

        # print leave_n, '/', len(tree._leaves), start, '/', len(tree._leaves[leave_n]), tree.__class__.__name__, tree.identifier,  match(tree.identifier, branch[0]), branch

        if branch[0] not in MATCH_ONE and not match(tree, branch[0]):
            return False
        else:
            if len(branch) + branch_n < 2:
                return True
            else:
                sub = branch[branch_n+1]
                if type(sub) is str:
                    region = None
                    for wild in WILDCARDS:
                        if wild in sub:
                            region = WILDCARDS[wild](sub)
                            break

                    if region is None:
                        raise ValueError('Parse error. ONLY ' + str(WILDCARDS.values()) + ' as wildcards allowed.')

                    if leave_n < len(leave_fnc(tree)):
                        leave = leave_fnc(tree)[leave_n]
                        if region.start <= len(leave):
                            # check that there are enough children to match
                            for left in range(*region.indices(len(leave) - 1)):
                                if cls._general_check_tree(tree, branch, match, leave_fnc, leave_n, start + left, branch_n + 1):
                                    return True

                else:
                    if leave_n < len(leave_fnc(tree)):
                        leave = leave_fnc(tree)[leave_n]

                        if len(leave) > start:
                            if cls._general_check_tree(leave[start], sub, match, leave_fnc):
                                # go to next sub in branch
                                if len(branch) - branch_n < 3:
                                    return True
                                else:
                                    if len(leave) > start + 1:
                                        return cls._general_check_tree(tree, branch, match, leave_fnc, leave_n, start + 1, branch_n + 1)


                if leave_n < len(leave_fnc(tree)) - 1:
                    if cls._general_check_tree(tree, branch, match, leave_fnc, leave_n + 1):
                        return True

                return False

    def _check_head_node(self, items):
        return self._check_tree(self, items, self._default_match)

    @staticmethod
    def _default_match(original, test):
        """
        A function determining the way single nodes are matched

        This function is used to test for __contains__

        Parameters
        ----------
        original : node
            the original node to be tested
        test : node-like
            the object a node should be tested for

        Returns
        -------
        bool
            True if the original is of type test. This depends on the
            actual implementation

        Notes
        -----
        Default is to test for equality `original == test`, often we might
        also allow for testing of classes, subclasses, e.g.
        [1,2,3] as a node could be tested for list and return True
        """
        if original == test:
            return True
        else:
            return False

    def __contains__(self, item):
        """
        Check if a node or a tree is in self

        The tree structure is as follows

        1. A tree consists of nodes
        2. Each node can have zero, one or more children
        3. Each child is a node itself

        The tree structure in openpathsampling is expressed as

        1. The tree structure is given as a nested list of lists ...
        2. The first element in the list is the node
        3. Element 2 to N are the children.
        4. Children are always wrapped in brackets

        node = [element, [child1], [child2], ... ]

        A tree can be a subtree if the subtree (always starting from the top)
        fits on top of the tree to match. Here child nodes are ignored as long
        as the mask of the subtree fits.

        In searching wildcards are allowed. This works as

        1. slice(start, end) means a number of arbitrary children between
            start and end-1
        2. '*' means an arbitrary number of arbitrary children. Equal to slice(0, None)
        3. None or '.' means ONE arbitrary child. Equal to slice(1,2)
        4. '?' means ONE or NONE arbitrary child. Equal to slice(0,2)
        5. 'n:m' is equal to slice(n,m), e.g. '0:3'

        Examples
        --------
        >>> tree1 = [mover1, [mover2]]
        >>> tree2 = [mover1, [mover2], [mover3]]
        >>> tree3 = [mover1, [mover2], [mover4, [mover5]]]
        >>> tree4 = []

        Parameters
        ----------
        item : node or tree
            the node or tree to be checked

        Returns
        -------
        bool
            True if the node is in the tree or if the subtree is in the tree

        """
        if type(item) is tuple or type(item) is list:
            return self._check_head_node(item)

            # Disable checking for submoves for now. I think we will not
            # use this ?!?

            # the head node did not fit so continue trying subnodes
#            for sub in self.subnodes:
#                if item in sub:
#                    return True
        else:
            for x in self:
                if self._default_match(x, item):
                    return True

        return False

    def tree(self):
        """
        Return the object as a tree structure of nested lists of nodes

        Returns
        -------
        nested list of nodes
            the tree in nested list format
        """
        return [self] + [ ch.tree() for ch in self._subnodes]

    def map_tree(self, fnc):
        """
        Apply a function to each node and return a nested tree of results

        Parameters
        ----------
        fnc : function(node, args, kwargs)
            the function run at each node node. It is given the node
            and the optional (fixed) parameters
        kwargs : named arguments
            optional arguments added to the function

        Returns
        -------
        tree (fnc(node, \*\*kwargs))
            nested list of the results of the map
        """
        return [fnc(self)] + [ ch.map_tree(fnc) for ch in self._subnodes]

    @property
    def identifier(self):
        """
        A unique identifier to build the unique key for a position in a tree

        Returns
        -------
        hashable object
            the unique (hashable) key to identify each node

        Notes
        -----
        This is often specific to the node type and hence overridden by the
        target tree
        """
        return hex(id(self))

    def keylist(self):
        """
        Return a list of key : subtree tuples

        Returns
        -------
        list of tuple(key, subtree)
            A list of all subtrees with their respective keys
        """
        path = [self.identifier]

        result = collections.OrderedDict()
        result[tuple(path)] = self
        excludes = []
        for leave in self._leaves:
            mp = []
            for pos, sub in enumerate(leave):
                subtree = sub.keylist()
                leave_id = tuple(map(lambda x : x.identifier, leave[:pos+1]))
                if leave_id not in excludes:
                    # print tuple(mp) == leave_id[:-1], tuple(mp), leave_id[:-1]
                    result.update(
                        {tuple(path + mp + [key]) : m for key, m in subtree.iteritems()}
                    )
                    excludes.append(leave_id)

                mp.append(tuple([sub.identifier]))

        return result

    def map_post_order(self, fnc, **kwargs):
        """
        Traverse the tree in post-order applying a function

        This traverses the underlying tree and applies the given function at
        each node returning a list of the results. Post-order means
        that subnodes are called BEFORE the node itself is evaluated.

        Parameters
        ----------
        fnc : function(node, kwargs)
            the function run at each node. It is given the node and the
            optional (fixed) parameters
        kwargs : named arguments
            optional arguments added to the function

        Returns
        -------
        list (fnc(node, \*\*kwargs))
            flattened list of the results of the map

        Notes
        -----
        This uses the same order as `reversed()`

        See also
        --------
        map_pre_order, map_post_order, level_pre_order, level_post_order
        """
        return [ fnc(node, **kwargs) for node in reversed(self) ]

    def depth_post_order(self, fnc, level=0, **kwargs):
        """
        Traverse the tree in post-order applying a function with depth

        This traverses the underlying tree and applies the given function at
        each node returning a list of the results. Post-order means
        that subnodes are called BEFORE the node itself is evaluated.

        Parameters
        ----------
        fnc : function(node, \*\*kwargs)
            the function run at each node. It is given the node and the
            optional (fixed) parameters
        level : int
            the initial level
        kwargs : named arguments
            optional arguments added to the function

        Returns
        -------
        list of tuple(level, func(node, \*\*kwargs))
            flattened list of tuples of results of the map. First part of
            the tuple is the level, second part is the function result.

        See also
        --------
        map_pre_order, map_post_order, level_pre_order, level_post_order
        """

        output = list()
        for mp in self._subnodes:
            output.extend(mp.depth_post_order(fnc, level + 1, **kwargs))
        output.append((level, fnc(self, **kwargs)))

        return output

    def map_pre_order(self, fnc, **kwargs):
        """
        Traverse the tree in pre-order applying a function

        This traverses the underlying tree applies the given function at
        each node returning a list of the results. Pre-order means
        that subnodes are called AFTER the node itself is evaluated.

        Parameters
        ----------
        fnc : function(node, \*\*kwargs)
            the function run at each node. It is given the node and the
            optional parameters
        kwargs : named arguments
            optional arguments added to the function

        Returns
        -------
        list (fnc(node, \*\*kwargs))
            flattened list of the results of the map

        Notes
        -----
        This uses the same order as `iter()`

        See also
        --------
        map_pre_order, map_post_order, level_pre_order, level_post_order
        """
        return [ fnc(node, **kwargs) for node in iter(self) ]

    def depth_pre_order(self, fnc, level=0, **kwargs):
        """
        Traverse the tree of node in pre-order applying a function

        This traverses the underlying tree applies the given function at
        each node returning a list of the results. Pre-order means
        that subnodes are called AFTER the node itself is evaluated.

        Parameters
        ----------
        fnc : function(node, \*\*kwargs)
            the function run at each node. It is given the node and the
            optional parameters
        level : int
            the initial level
        kwargs : named arguments
            optional arguments added to the function

        Returns
        -------
        list of tuple(level, fnc(node, \*\*kwargs))
            flattened list of tuples of results of the map. First part of
            the tuple is the level, second part is the function result.

        See also
        --------
        map_pre_order, map_post_order, level_pre_order, level_post_order
        """

        output = list()
        output.append((level, fnc(self, **kwargs)))

        for mp in self._subnodes:
            output.extend(mp.depth_pre_order(fnc, level + 1, **kwargs))

        return output

class TupleTree(tuple):

    @staticmethod
    def contains(needle, haystack):
        def cmp_fnc(x, y):
            return x[0] is y

        def leave_fnc(x):
            return [x[1:]]

        return TreeSetMixin._general_check_tree(haystack, needle, cmp_fnc, leave_fnc)

    def __contains__(self, item):
        return self.contains(item, self)

    def __str__(self):
        return TupleTree.treeprint(self)

    @staticmethod
    def treeprint(x):
        return str(x[0]) + "\n" + TreeSetMixin._indent("\n".join(map(TupleTree.treeprint, x[1:])))