import lmql
import asyncio
from typing import List, Tuple, Callable

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

class TreeOfThoughts:
    def __init__(
        self,
        graded_criteria: List[str],
        vital_criteria: List[str],
        fatal_criteria: List[str],
        validations: List[Tuple[str, bool] | Callable]=[],
        callback_prompt: str="",
        callback_fn: Callable=None,
        **kwargs):
        '''
        n_active: number of active thoughts to consider at each step
        n_child_thoughts: number of child thoughts to generate for each active thought
        max_iterations: maximum number of iterations to run before giving up

        Each iteration creates and evalutates n_active*n_child_thought new thoughts.
        Abandons if a solution isn't found within max_iterations.
        '''
        self.n_active = 1
        self.n_child_thoughts = 3
        self.max_iterations = 20
        self.decay = 0.99

        self.validations = validations
        self.callback_prompt = callback_prompt
        self.callback_fn = callback_fn

        self.graded_criteria = graded_criteria # TODO: Investigate relative scoring scheme
        self.vital_criteria = vital_criteria
        self.fatal_criteria = fatal_criteria

        self.penalties = [] # TODO: investigate if these are useful, would add into evaluations
        self.bonuses = []

        self.params = {criteria: (1, 0) for criteria in self.graded_criteria} # TODO: use these in self.process_rating

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
        root = "Question: " + question +"\nAnswer: Let's think step by step."
        self.root = root
        if verbose:
            self.verbose_buffer += color['cyan']( "ROOT ------------------------------------------------------\n")
            self.verbose_buffer += root + "\n\n"
            self.print_verbose()

        self.tree = {self.root: []}
        self.root = root
        self.leafs_that_are["active"] = []
        self.leafs_that_are["dead"] = []
        self.viable_leafs = {root: 1e-3}

        current = 1
        answers = []

        # TODO: export loop contents to self.step()
        while current <= self.max_iterations:
            self.viable_leafs = {k: v * self.decay for k, v in self.viable_leafs.items()}

            # root can't die
            if not self.viable_leafs:
                self.viable_leafs = {root: 1e-3}

            if verbose:
                self.verbose_buffer += color['green'](f"ITERATION {current} VIABLE LEAF THOUGHTS\n")
                if not self.viable_leafs:
                    self.verbose_buffer += "    (No surviving leafs)\n\n"
                for thought, score in self.viable_leafs.items():
                    self.verbose_buffer += f"    {score}: {thought}\n"
                self.verbose_buffer += "\n"
                self.print_verbose()

            # Determine if any leafs are ready to be answered
            if verbose:
                self.verbose_buffer += color['cyan']( "CHECKING FOR ANSWERABLE THOUGHTS --------------------------\n")
                self.print_verbose()
            leaf_thoughts = []
            reasoning_paths = []
            can_answer = []

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
                self.verbose_buffer += color['cyan']("\n------------------------------\n").join([reasoning_path + "\n" + color['blue'](leaf_thought) + "\n" for leaf_thought, reasoning_path in zip(leaf_thoughts, reasoning_paths)]) + "\n"
                self.print_verbose()

            for leaf_thought, reasoning_path, can_answer in zip(leaf_thoughts, reasoning_paths, can_answer):
                if can_answer:
                    next_thoughts_list.append(self.final_result(reasoning_path + "\n" + leaf_thought))
                    answer_leafs.append(leaf_thought)
                    n_answers += 1
                    n_thoughts += 1
                else:
                    next_thoughts_list.append(self.get_next_thoughts(self.n_child_thoughts, reasoning_path + "\n" + leaf_thought))
                    n_thoughts += self.n_child_thoughts

            next_thoughts_list = await asyncio.gather(*next_thoughts_list)
            next_thoughts_list = [x if isinstance(x[0], str) else [y[0] for y in x] for x in next_thoughts_list]

            if verbose:
                self.verbose_buffer += f"  {n_thoughts} new thoughts from here\n" 
                self.verbose_buffer += f"  {n_answers} of which are potential answers\n\n"
                self.print_verbose()

            # Prune leafs with bad reasoning, save good ones to the tree
            if verbose:
                self.verbose_buffer += color['cyan']( "ASSESSING THOUGHT PATHS -----------------------------------\n")
                self.print_verbose()

            thought_ratings_list = []
            for leaf_thought, reasoning_path, next_thoughts in zip(leaf_thoughts, reasoning_paths, next_thoughts_list):
                if leaf_thought not in answer_leafs:
                    thought_ratings_list.append(asyncio.gather(*[self.evaluate_reasoning(reasoning_path + "\n" + leaf_thought + "\n" + next_thought) for next_thought in next_thoughts]))
                else:
                    thought_ratings_list.append(*[self.validate_result(next_thoughts[0])]) # attempted answers only have one branch

            thought_ratings_list = await asyncio.gather(*thought_ratings_list)
            thought_ratings_list = [x if isinstance(x, list) else [x] for x in thought_ratings_list]

            if verbose:
                n_true = 0
                for thought_ratings in thought_ratings_list:
                    for thought_rating in thought_ratings:
                        if thought_rating > 0:
                            n_true += 1
                self.verbose_buffer += f"  {n_true}/{n_thoughts} of the new thoughts are viable\n"
                self.print_verbose()

            for leaf_thought, next_thoughts, thought_ratings in zip(leaf_thoughts, next_thoughts_list, thought_ratings_list):
                '''
                Every node in the tree has either been given a viability score, or marked as a deadend.
                A leaf thought is always initilaized as a list, which points to all of its next_thoughts.
                Its next thoughts are either added to answer leafs, or its score is saved in viable_leafs, or goes into leafss that are dead.
                '''
                if not leaf_thought in self.tree:
                    self.tree[leaf_thought] = []

                for next_thought, thought_rating in zip(next_thoughts, thought_ratings):
                    self.tree[leaf_thought].append(next_thought)
                    if thought_rating > 0: # thought survival threshold
                        if leaf_thought in answer_leafs: # answer survived validation
                            answers.append(next_thought)
                        if next_thought not in self.viable_leafs:
                            self.viable_leafs[next_thought] = thought_rating # leaf survived evaluation
                    else:
                        self.leafs_that_are["dead"].append(next_thought)

                    if leaf_thought in self.viable_leafs:
                        del self.viable_leafs[leaf_thought]

            if verbose:
                self.verbose_buffer += f"  {len(answers)} answers passing validation\n\n"
                self.print_verbose()

            current += 1

            if answers:
                if print_tree:
                    self.print_tree()
                return answers

        if verbose:
            self.verbose_buffer += color['cyan']( "NO ANSWERS FOUND ------------------------------------------\n\n")
            self.print_verbose()
            if print_tree:
                self.print_tree()

    def traverse(self, node, path=None):
        '''
        returns all of the paths from the root to the leaves of the tree
        as a list of (thought, reasoning) tuples
        '''
        if not path:
            path = []

        if node not in self.tree: # move
            return [(node, "\n".join(path))]
        else:
            if node in self.leafs_that_are["dead"]:
                return []

            path.append(node)
            paths = []
            for child in self.tree[node]:
                paths += self.traverse(child, path[:])

            if node == self.root and not paths:
                return [(self.root, "")]

            return paths

    @lmql.query
    async def final_result(self, reasoning):
        '''lmql
        sample()
            "{reasoning}\n"
            "{self.callback_prompt}"
            "[result]"
            if self.callback_fn:
                return self.callback_fn(result)
            return result
        from
            "openai/gpt-3.5-turbo"
        # where
        #     STOPS_AT(result, ".")
        '''

    async def validate_result(self, result):
        if self.validations:
            validation_failures = []
            for validation in self.validations:
                if isinstance(validation, tuple):
                    validation_failures.append(self.prompt_validate(result, validation[0], validation[1]))
                else:
                    validation_failures.append(validation(result))

            validation_failures = await asyncio.gather(*validation_failures)
            validation_failures = [x[0] if isinstance(x, list) else x for x in validation_failures]

            if any(validation_failures):
                return 0 # below survival threshold

        return 1 # above survival threshold

    @lmql.query
    async def prompt_validate(self, result, validation, should_be):
        """lmql
        argmax
            "{result}\n"
            "{validation} (yes/no)\n"
            "[yn]"
            # self.verbose_buffer += f"    {result} {validation}?: {yn} should be {should_be}\n"
            if yn.split()[-1]  in ["yes", "Yes"]:
                return not should_be
            return should_be
        from
            "openai/gpt-3.5-turbo"
        where
            STOPS_AT(yn, "yes") and
            STOPS_AT(yn, "no") and
            STOPS_AT(yn, "Yes") and
            STOPS_AT(yn, "No") and
            len(TOKENS(yn)) < 20
        """

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

    # TODO: use self.stopping_prompt
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

    # TODO: programatic constraints
    # TODO: explore metaprompting for rating criteria
    async def evaluate_reasoning(self, reasoning):
        fatal_flags = [self.bool_classify(statement, reasoning, should_be=False) for statement in self.fatal_criteria]
        fatal_flags += [self.bool_classify(statement, reasoning, should_be=True) for statement in self.vital_criteria]
        fatal_flags = await asyncio.gather(*fatal_flags)
        fatal_flags = [x[0] for x in fatal_flags]
        if any(fatal_flags):
            # self.verbose_buffer += "  fatal rejection\n"
            return 0

        evaluations = [self.grade(statement, reasoning) for statement in self.graded_criteria]
        evaluations = await asyncio.gather(*evaluations)
        evaluations = [x[0] for x in evaluations]
        # self.verbose_buffer += "  " + str(evaluations)
        # self.verbose_buffer += f"  scored {sum(evaluations)}\n"

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

    # TODO: replace ridiculous list of stops_at constraints if "in" constraints are supported for chat
    @lmql.query
    async def grade(self, statement, reasoning):
        '''lmql
        argmax
            "Please assess the following reasoning, and choose an option for each point. "
            "1 means fully disagree, 9 means fully agree, 5 means neutral or no information:\n\n"
            "```\n"
            "{reasoning}\n"
            "```\n\n"
            "{statement} (1 - 9): [rating]"
            if rating[-1] in [str(i) for i in range(1,10)]:
                rating = int(rating[-1])
                rating = rating - 5
            else:
                self.verbose_buffer += "didn't end in number\n"
                rating = 0 # no information

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
