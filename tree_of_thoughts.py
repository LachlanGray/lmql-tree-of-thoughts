import lmql
import asyncio

color= {
    "black": lambda text: f"\033[30m{text}\033[0m",
    "red": lambda text: f"\033[31m{text}\033[0m",
    "green": lambda text: f"\033[32m{text}\033[0m",
    "yellow": lambda text: f"\033[33m{text}\033[0m",
    "blue": lambda text: f"\033[34m{text}\033[0m",
    "magenta": lambda text: f"\033[35m{text}\033[0m",
    "cyan": lambda text: f"\033[36m{text}\033[0m",
    "white": lambda text: f"\033[37m{text}\033[0m",
}

# TODO: unique identifiers for thoughts
# TODO: debug output writer

@lmql.query_class
class TreeOfThoughts:
    def __init__(self, graded_criteria, vital_criteria, fatal_criteria, **kwargs):
        '''
        n_active: number of active thoughts to consider at each step
        n_child_thoughts: number of child thoughts to generate for each active thought
        max_iterations: maximum number of iterations to run before giving up

        Each iteration creates and evalutates n_active*n_child_thought new thoughts.
        Abandons if a solution isn't found within max_iterations.
        '''
        self.n_active = 3
        self.n_child_thoughts = 3
        self.max_iterations = 10

        self.graded_criteria = graded_criteria # TODO: Try using top scorers as references, everything usually gets full marks
        self.vital_criteria = vital_criteria   #       - A global scaling factor on top of the scores could allow full scores to get reduced
        self.fatal_criteria = fatal_criteria   #       - a decaying factor each loop on all scores; unexplored leaf thoughts implicitly less important

        self.penalties = [] # TODO: investigate if these are useful, would add into evaluations
        self.bonuses = []

        self.params = {criteria: (1, 0) for criteria in self.graded_criteria} # TODO: use these in self.process_rating

        self.params.update(kwargs)

        self.tree = {}
        self.root = ""
        self.answers = []
        self.leafs_that_are = {
            "active": [],
            "viable": [],
            "dead": [],
        }

        # TODO: memory, error propagation

        self.viable_leafs = {}

        self.verbose_buffer = ""


    def reason(self, question, verbose=False, print_tree=False):
        return asyncio.run(self._reason(question, verbose, print_tree))

    def print_verbose(self):
        # clear screen
        print("\033c", end="")
        print(self.verbose_buffer)

    def print_tree(self, parent=None, level=0, visited=None):
        if visited is None:
            visited = set()

        if parent is None:
            for parent in (k for k in self.tree if not any(k in v for v in self.tree.values())):
                self.print_tree(parent, level, visited)
        else:
            print('  ' * level, parent)
            visited.add(parent)
            for child in self.tree.get(parent, []):
                if child not in visited:
                    self.print_tree(child, level + 1, visited)

    async def _reason(self, question, verbose, print_tree):
        # TODO: definable pre/post script, move this to init
        root = "Question: " + question +". \nAnswer: Let's think step by step."
        self.root = root
        if verbose:
            self.verbose_buffer += color['cyan']( "ROOT ------------------------------------------------------\n")
            self.verbose_buffer += root + "\n\n"
            self.print_verbose()

        self.tree = {self.root: []}
        self.root = root
        self.leafs_that_are["active"] = []
        self.leafs_that_are["dead"] = []
        self.viable_leafs = {root: 1}

        current = 1
        answers = []

        # TODO: export loop contents to self.step()
        while current <= self.max_iterations:
            if verbose:
                self.verbose_buffer += color['green'](f"ITERATION {current}\n")
                # self.verbose_buffer += "Leaf scores from previous iterations:\n"
                # if not self.viable_leafs:
                #     self.verbose_buffer += "    (No surviving leafs)\n"
                # for thought, score in self.viable_leafs.items():
                #     self.verbose_buffer += f"    {score}: {thought}\n"
                self.print_verbose()

            # Determine if any leafs are ready to be answered
            if verbose:
                self.verbose_buffer += color['cyan']( "CHECKING FOR ANSWERABLE THOUGHTS --------------------------\n")
                self.print_verbose()
            leaf_thoughts = []
            reasoning_paths = []
            can_answer = []

            # root can't die
            if not self.viable_leafs:
                self.viable_leafs = {root: 1}

            self.leafs_that_are["active"] = sorted(self.viable_leafs, key=self.viable_leafs.get, reverse=True)[:self.n_active]

            # self.verbose_buffer += str(self.traverse(self.root))
            for leaf_thought, reasoning_path in self.traverse(self.root):
                if leaf_thought and leaf_thought not in self.leafs_that_are["active"]:
                    continue

                leaf_thoughts.append(leaf_thought)
                reasoning_paths.append(reasoning_path)
                can_answer.append(self.can_answer(reasoning_path + "\n" + leaf_thought))

            can_answer = await asyncio.gather(*can_answer)
            can_answer = [x[0] for x in can_answer]

            if verbose:
                # self.verbose_buffer +=  color['red']("active nodes:\n    * " ) + color['red']("\n    *").join(self.leafs_that_are["active"]) + "\n\n"
                # self.verbose_buffer += "\n    -> " + color['red']("\n    -> ").join([color['red'](str(a)) for a in can_answer]) + "\n\n"
                self.verbose_buffer += f"  {sum(can_answer)} answerable thoughts found\n\n"
                self.print_verbose()

            # Generate next thoughts and/or answers
            if verbose:
                self.verbose_buffer += color['cyan']( "GENERATING NEXT THOUGHTS ----------------------------------\n")
                self.print_verbose()

            next_thoughts_list = []
            answer_leafs = []
            n_thoughts = 0
            n_answers = 0
            if verbose:
                # self.verbose_buffer += color['cyan']("\n***\n").join([reasoning_path + "\n" + color['blue'](leaf_thought) + "\n\nReady to answer: " + str(can_answer) + "\n"for leaf_thought, reasoning_path, can_answer in zip(leaf_thoughts, reasoning_paths, can_answer)])
                self.verbose_buffer += color['cyan']("\n------------------------------").join([reasoning_path + "\n" + color['blue'](leaf_thought) + "\n" for leaf_thought, reasoning_path in zip(leaf_thoughts, reasoning_paths)]) + "\n"
                self.print_verbose()

            for leaf_thought, reasoning_path, can_answer in zip(leaf_thoughts, reasoning_paths, can_answer):
                if can_answer:
                    next_thoughts_list.append(self.final_answer(reasoning_path + "\n" + leaf_thought))
                    answer_leafs.append(leaf_thought)
                    n_answers += 1
                else:
                    next_thoughts_list.append(self.get_next_thoughts(self.n_child_thoughts, reasoning_path + "\n" + leaf_thought))
                    n_thoughts += self.n_child_thoughts

            next_thoughts_list = await asyncio.gather(*next_thoughts_list)
            next_thoughts_list = [x if isinstance(x[0], str) else [y[0] for y in x] for x in next_thoughts_list]

            if verbose:
                self.verbose_buffer += f"  {n_thoughts} new thoughts\n" 
                self.verbose_buffer += f"  {n_answers} potential answers\n\n"
                self.print_verbose()

            # Prune leafs with bad reasoning, save good ones to the tree
            if verbose:
                self.verbose_buffer += color['cyan']( "ASSESSING THOUGHT PATHS -----------------------------------\n")
                self.print_verbose()

            thought_ratings_list = []
            # TODO: zip with can_answer to call a distinct answer assessment prompt for answer leafs
            for leaf_thought, reasoning_path, next_thoughts in zip(leaf_thoughts, reasoning_paths, next_thoughts_list):
                thought_ratings_list.append(asyncio.gather(*[self.evaluate_reasoning(reasoning_path + "\n" + leaf_thought + "\n" + next_thought) for next_thought in next_thoughts]))

            thought_ratings_list = await asyncio.gather(*thought_ratings_list)

            if verbose:
                n_true = 0
                n_false = 0
                for thought_ratings in thought_ratings_list:
                    for thought_rating in thought_ratings:
                        if thought_rating > 0:
                            n_true += 1
                        else:
                            n_false += 1
                self.verbose_buffer += f"  {n_true} viable new thoughts\n"
                self.verbose_buffer += f"  {n_false} rejected\n"
                self.print_verbose()

            for leaf_thought, next_thoughts, thought_ratings in zip(leaf_thoughts, next_thoughts_list, thought_ratings_list):
                if not leaf_thought in self.tree:
                    self.tree[leaf_thought] = []

                for next_thought, thought_rating in zip(next_thoughts, thought_ratings):
                    self.tree[leaf_thought].append(next_thought)
                    if thought_rating > 0: # thought survival threshold
                        if next_thought not in self.viable_leafs:
                            self.viable_leafs[next_thought] = thought_rating
                    else:
                        self.leafs_that_are["dead"].append(next_thought)
                    if leaf_thought in self.viable_leafs:
                        del self.viable_leafs[leaf_thought]


            # Check if any answer leafs succeeded
            # TODO: (user defined ) callback queries and functions to filter answers
            n_successful_answers = 0
            for answer_leaf in answer_leafs:
                if answer_leaf in self.tree: # failed answer leafs are deleted by now
                    answers.append(self.tree[answer_leaf][0])
                    n_successful_answers += 1

            if verbose:
                self.verbose_buffer += f"  {n_successful_answers} accepted answers\n\n"
                self.print_verbose()

            current += 1

            if answers:
                if print_tree:
                    self.print_tree()
                # TODO: if multiple choose highest rating or select with judge query
                return answers

        if verbose:
            self.verbose_buffer += color['cyan']( "NO ANSWERS FOUND ------------------------------------------\n\n")
            self.print_verbose()
            self.print_tree()

    def traverse(self, node, path=None):
        '''
        returns all of the paths from the root to the leaves of the tree
        as a list of (thought, reasoning) tuples
        '''
        if not path:
            path = []

        if node not in self.tree:
            if node in self.leafs_that_are["dead"]:
                return []
            return [(node, "\n".join(path))]
        else:
            # if node == self.root and not self.tree[self.root]:
            #     return [("", self.root)]

            # if all([x in self.leafs_that_are["dead"] for x in self.tree[node]]):
            #     return []

            path.append(node)
            paths = []
            for child in self.tree[node]:
                paths += self.traverse(child, path[:])

            if node == self.root and not paths:
                return [(self.root, "")]

            return paths

    # TODO: user specified conclusion prompt
    @lmql.query
    async def final_answer(self, reasoning):
        '''lmql
        sample()
            "{reasoning}\n\n"
            "In a sentence the answer is [answer]."
            if "\n" not in answer:
                return answer
            else:
                return answer.split("\n")[-1]
        from
            "openai/gpt-3.5-turbo"
        where
            STOPS_AT(answer, ".")
        '''

    async def get_next_thoughts(self, n, reasoning):
        thoughts = [self.get_next_thought(reasoning) for _ in range(n)]
        return await asyncio.gather(*thoughts)

    @lmql.query
    async def get_next_thought(self, reasoning, ):
        '''lmql
        sample()
            "{reasoning}\n"
            "[thought]"
            return thought
        from 
            "openai/gpt-3.5-turbo"
        where 
            STOPS_BEFORE(thought, "\\n") and 
            STOPS_BEFORE(thought, "\n") and 
            STOPS_BEFORE(thought, ".")
        '''

    @lmql.query
    async def can_answer(self, reasoning):
        '''lmql
        argmax
            "Has the following reasoning achieved a correct and satisfying answer to the initial question? yes or no?\n"
            # "Is the following answer complete? yes or no?\n"
            "```\n"
            "{reasoning}"
            "```\n\n"
            "[yn]"
            if yn.split()[-1] in ["yes", "Yes"]:
                return True
            else:
                return False
        from 
            "openai/gpt-3.5-turbo"
        where
            STOPS_AT(yn, "yes") and
            STOPS_AT(yn, "no") and
            STOPS_AT(yn, "Yes") and
            STOPS_AT(yn, "No") and
            len(TOKENS(yn)) < 20
        '''

    # TODO: user defined rating criteria for generic use cases
    # TODO: user defined validations (prompted and programmed)
    # TODO: penalties/bonuses
    # TODO: explore metaprompting for rating criteria
    # TODO: replace ridiculous list of stops_at constraints if "in" constraints are supported for chat
    async def evaluate_reasoning(self, reasoning):
        fatal_flags = [self.bool_classify(statement, reasoning, should_be=False) for statement in self.fatal_criteria]
        fatal_flags += [self.bool_classify(statement, reasoning, should_be=True) for statement in self.vital_criteria]
        fatal_flags = await asyncio.gather(*fatal_flags)
        fatal_flags = [x[0] for x in fatal_flags]
        if any(fatal_flags):
            return 0

        evaluations = [self.grade(statement, reasoning) for statement in self.graded_criteria]
        evaluations = await asyncio.gather(*evaluations)
        evaluations = [x[0] for x in evaluations]

        return sum(evaluations)

    @lmql.query
    async def bool_classify(self, statement, reasoning, should_be=True):
        '''lmql
        argmax
            # returns 0 if the statement evaluates as it should, otherwise 1
            default = "yes" if should_be else "no"
            "Please assess the following reasoning, and choose an option for each point. If a question is not applicable, default to {default}:\n\n"
            "```\n"
            "{reasoning}\n"
            "```\n\n"
            "{statement} (yes/no): [yn]"
            if yn.split()[-1] in ["yes", "Yes"]:
                return not should_be
            else:
                return should_be
        from
            "openai/gpt-3.5-turbo"
        where
            STOPS_AT(yn, "yes") and
            STOPS_AT(yn, "no") and
            STOPS_AT(yn, "Yes") and
            STOPS_AT(yn, "No") and
            len(TOKENS(yn)) < 10
        '''

    @lmql.query
    async def grade(self, statement, reasoning):
        '''lmql
        argmax
            "Please assess the following reasoning, and choose an option for each point. If a question is not applicable, default to 5:\n\n"
            "```\n"
            "{reasoning}\n"
            "```\n\n"
            "{statement} (1 - 9): [rating]"
            if rating[-1] in set(range(1,10)):
                rating = int(rating[-1])
            else:
                rating = 5 # no information

            return rating
        from 
            "openai/gpt-3.5-turbo"
        where
            STOPS_AT(rating, "1") and
            STOPS_AT(rating, "2") and
            STOPS_AT(rating, "3") and
            STOPS_AT(rating, "4") and
            STOPS_AT(rating, "5") and
            STOPS_AT(rating, "6") and
            STOPS_AT(rating, "7") and
            STOPS_AT(rating, "8") and
            STOPS_AT(rating, "9") and
            len(TOKENS(rating)) < 10
        '''
