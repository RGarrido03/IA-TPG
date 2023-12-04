from abc import ABC, abstractmethod


class SearchDomain(ABC):

    # Construtor
    @abstractmethod
    def __init__(self):
        pass

    # Possible actions in a state
    @abstractmethod
    def actions(self, state):
        pass

    # Result of an action over a state, i.e., the new state
    @abstractmethod
    def result(self, state, action):
        pass

    # Cost of an action
    @abstractmethod
    def cost(self, state, action):
        pass

    # Estimated cost from a state to another
    @abstractmethod
    def heuristic(self, state, goal):
        pass

    # Test if the given "goal" is satisfied in "state"
    @abstractmethod
    def satisfies(self, state, goal):
        pass


# Needed-to-be-solved problem in a certain domain
class SearchProblem:
    def __init__(self, domain, initial, goal):
        self.domain = domain
        self.initial = initial
        self.goal = goal

    def goal_test(self, state):
        return self.domain.satisfies(state, self.goal)


# Search tree nodes
class SearchNode:
    def __init__(self, state, parent, depth, cost, heuristic, plan):
        self.state = state
        self.parent = parent
        self.depth = depth
        self.cost = cost
        self.heuristic = heuristic
        self.plan = plan

    def in_parent(self, newstate):
        if self.parent is None:
            return False
        if self.parent.state == newstate:
            return True
        return self.parent.in_parent(newstate)

    def __str__(self):
        return "no(" + str(self.state) + "," + str(self.parent) + ")"

    def __repr__(self):
        return str(self)


# Arvores de pesquisa
class SearchTree:

    # construtor
    def __init__(self, problem, strategy='breadth'):
        self.problem = problem
        root = SearchNode(problem.initial, None, 0, 0, problem.domain.heuristic(problem.initial, problem.goal), ())
        self.open_nodes = [root]
        self.strategy = strategy
        self.solution = None
        self.non_terminals = 0
        self.highest_cost_nodes = [root]
        self.average_depth = root.depth
        self.plan = []

    @property
    def terminals(self):
        return len(self.open_nodes) + 1

    @property
    def length(self):
        return self.solution.depth

    @property
    def avg_branching(self):
        return (self.non_terminals + self.terminals - 1) / self.non_terminals

    @property
    def cost(self):
        return self.solution.cost

    # Get the path from the root to a node
    def get_path(self, node):
        if node.parent is None:
            return [node.state]
        path = self.get_path(node.parent)
        path += [node.state]
        self.plan += [node.plan]
        return path

    # Find the solution
    def search(self, limit=None):
        print("State\tCost\tHeuristic\tDepth\tPlan")
        while self.open_nodes:
            node = self.open_nodes.pop(0)
            print(
                f"{node.state}\t{node.cost}\t{node.heuristic}\t\t{node.depth}\t{node.plan}"
            )

            if self.problem.goal_test(node.state):
                self.solution = node
                self.average_depth /= self.terminals + self.non_terminals
                return self.get_path(node)

            self.non_terminals += 1
            lnewnodes = []

            for a in self.problem.domain.actions(node.state):
                newstate = self.problem.domain.result(node.state, a)
                if not node.in_parent(newstate) and (limit is None or node.depth < limit):
                    newnode = SearchNode(newstate, node, node.depth + 1,
                                         node.cost + self.problem.domain.cost(node.state, a),
                                         self.problem.domain.heuristic(newstate, self.problem.goal), a)
                    self.average_depth += newnode.depth

                    if newnode.cost > self.highest_cost_nodes[0].cost:
                        self.highest_cost_nodes = [newnode]
                    elif newnode.cost == self.highest_cost_nodes[0].cost:
                        self.highest_cost_nodes.append(newnode)

                    lnewnodes.append(newnode)

            self.add_to_open(lnewnodes)
        return None

    # Add new nodes to 'open_nodes' list depending on the chosen strategy
    def add_to_open(self, lnewnodes):
        if self.strategy == 'breadth':
            self.open_nodes.extend(lnewnodes)
        elif self.strategy == 'depth':
            self.open_nodes[:0] = lnewnodes
        elif self.strategy == 'uniform':
            self.open_nodes.extend(lnewnodes)
            self.open_nodes.sort(key=lambda n: n.cost)
        elif self.strategy == 'greedy':
            self.open_nodes.extend(lnewnodes)
            self.open_nodes.sort(key=lambda n: n.heuristic)
        elif self.strategy == 'a*':
            self.open_nodes.extend(lnewnodes)
            self.open_nodes.sort(key=lambda n: n.cost + n.heuristic)
