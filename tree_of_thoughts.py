import lmql
import asyncio
from collections import namedtuple

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

PromptSandwich = namedtuple("PromptSandwich", ["prefix", "suffix", "items"])
ReasoningPrompt = namedtuple("ReasoningPrompt", ["graded", "vital", "fatal", "stopping"])
AnswerPrompt = namedtuple("AnswerPrompt", ["callback_prompt", "callback_fn", "validation"])

def create_prompt_sandwich(data):
    prefix = data.get("prefix", "")
    suffix = data.get("suffix", "")
    items = data.get("items", [])
    return PromptSandwich(prefix=prefix, suffix=suffix, items=items)

def create_prompt_reasoning(data):
    graded = create_prompt_sandwich(data.get("graded", {}))
    vital = create_prompt_sandwich(data.get("vital", {}))
    fatal = create_prompt_sandwich(data.get("fatal", {}))
    stopping = create_prompt_sandwich(data.get("stopping", {}))
    return ReasoningPrompt(graded=graded, vital=vital, fatal=fatal, stopping=stopping)

def create_prompt_answer(data):
    callback_prompt = create_prompt_sandwich(data.get("callback_prompt", {}))
    callback_fn = data.get("callback_fn", None)
    validation = create_prompt_sandwich(data.get("validation", {}))
    return AnswerPrompt(callback_prompt=callback_prompt, callback_fn=callback_fn, validation=validation)

class TreeOfThoughts:
    initial: PromptSandwich
    reasoning: ReasoningPrompt
    answer: AnswerPrompt

    def __init__(self, initial, reasoning, answer):

        self.initial = create_prompt_sandwich(initial)
        self.reasoning = create_prompt_reasoning(reasoning)
        self.answer = create_prompt_answer(answer)

        self.n_active = 1
        self.n_child_thoughts = 3
        self.max_iterations = 10
        self.decay = 0.99

        self.penalties = [] # TODO: investigate if these are useful, would add into evaluations
        self.bonuses = []

        # self.params = {criteria: (1, 0) for criteria in self.graded_criteria} # TODO: use these in self.process_rating

        self.tree = {}
        self.root = ""
        self.answers = []
        self.leafs_that_are = {
            "active": set(),
            "viable": set(),
            "dead": set(),
        }

        # TODO: memory, error propagation

        self.viable_leafs = {}

        self.verbose_buffer = ""

    def reason(self, argument, verbose=False, print_tree=False):
        return asyncio.run(self._reason(argument, verbose, print_tree))

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

    async def _reason(self, argument, verbose, print_tree):
        root = self.initial.prefix + argument + self.initial.suffix
        self.root = root

        if verbose:
            self.verbose_buffer += color['cyan']( "ROOT ------------------------------------------------------\n")
            self.verbose_buffer += root + "\n\n"
            self.print_verbose()

        self.tree = {self.root: []}
        self.root = root
        self.leafs_that_are["active"] = set()
        self.leafs_that_are["dead"] = set()
        self.viable_leafs = {self.root: 1e-3}

        current = 1
        answers = []

        # TODO: export loop contents to self.step()
        while current <= self.max_iterations:
            self.viable_leafs = {k: v * self.decay for k, v in self.viable_leafs.items()}

            if verbose:
                self.verbose_buffer += color['green'](f"ITERATION {current} VIABLE LEAF THOUGHTS\n")
                if not self.viable_leafs:
                    self.verbose_buffer += "    (No surviving leafs)\n\n"
                for thought in self.viable_leafs.keys():
                    self.verbose_buffer += f"    {thought}\n"
                self.verbose_buffer += "\n"
                self.print_verbose()

            # Determine if any leafs are ready to be answered
            if verbose:
                self.verbose_buffer += color['cyan']( "CHECKING FOR ANSWERABLE THOUGHTS --------------------------\n")
                self.print_verbose()

            selected_leaf_thoughts = []
            reasoning_paths = []
            can_answer = []

            self.viable_leafs
            self.leafs_that_are["active"] = sorted(self.viable_leafs, key=self.viable_leafs.get, reverse=True)[:self.n_active]

            # TODO: iterate over viable_leafs instead
            for leaf_thought, reasoning_path in self.traverse(self.root):
                if leaf_thought not in self.leafs_that_are["active"]:
                    continue

                selected_leaf_thoughts.append(leaf_thought)
                reasoning_paths.append(reasoning_path)
                can_answer.append(self.is_finished(reasoning_path + "\n" + leaf_thought))

            if not selected_leaf_thoughts:
                selected_leaf_thoughts.append(self.root)
                reasoning_paths.append("")
                can_answer.append(self.is_finished(self.root))


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
                self.verbose_buffer += color['cyan']("\n------------------------------\n").join([reasoning_path + "\n" + color['blue'](leaf_thought) + "\n" for leaf_thought, reasoning_path in zip(selected_leaf_thoughts, reasoning_paths)]) + "\n"
                self.print_verbose()

            for leaf_thought, reasoning_path, can_answer in zip(selected_leaf_thoughts, reasoning_paths, can_answer):
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
            for leaf_thought, reasoning_path, next_thoughts in zip(selected_leaf_thoughts, reasoning_paths, next_thoughts_list):
                if leaf_thought not in answer_leafs:
                    thought_ratings_list.append(asyncio.gather(*[self.evaluate_reasoning(reasoning_path + "\n" + leaf_thought + "\n" + next_thought) for next_thought in next_thoughts]))
                else:
                    thought_ratings_list.append(*[self.validate_result(next_thoughts[0])]) # attempted answers only have one branch

            thought_ratings_list = await asyncio.gather(*thought_ratings_list)
            thought_ratings_list = [x if isinstance(x, list) else [x] for x in thought_ratings_list]

            if verbose:
                self.verbose_buffer += "  new thought scores: "
                n_true = 0
                for thought_ratings in thought_ratings_list:
                    for next_thought_rating in thought_ratings:
                        self.verbose_buffer += str(next_thought_rating) + ", "
                        if next_thought_rating > 0:
                            n_true += 1
                self.verbose_buffer += "\n"
                self.verbose_buffer += f"  {n_true}/{n_thoughts} of the new thoughts are viable\n"
                self.print_verbose()

            for leaf_thought, next_thoughts, thought_ratings in zip(selected_leaf_thoughts, next_thoughts_list, thought_ratings_list):
                '''
                Every node in the tree has either been given a viability score, or marked as a deadend.
                A leaf thought is always initilaized as a list, which points to all of its next_thoughts.
                Its next thoughts are either added to answer leafs, or its score is saved in viable_leafs, or goes into leafss that are dead.
                '''
                if not leaf_thought in self.tree:
                    self.tree[leaf_thought] = []

                for next_thought, next_thought_rating in zip(next_thoughts, thought_ratings):
                    self.tree[leaf_thought].append(next_thought)
                    if next_thought_rating > 0: # thought survival threshold
                        if leaf_thought in answer_leafs: # answer survived validation
                            answers.append(next_thought)
                          # and next_thought not in self.leafs_that_are["dead"]
                        if next_thought not in self.viable_leafs:
                            self.viable_leafs[next_thought] = next_thought_rating # leaf survived evaluation
                    else:
                        self.leafs_that_are["dead"].add(next_thought)

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

    # TODO: build from leafs not root
    def traverse(self, node, path=None):
        '''
        returns all of the paths from the root to the leaves of the tree
        as a list of (thought, reasoning) tuples
        '''
        if not path:
            path = []

        if node not in self.tree: # is a leaf
            if node in self.leafs_that_are["dead"]:
                return []
            return [(node, "\n".join(path))]
        else:

            path.append(node)
            child_paths = []
            for child in self.tree[node]:
                child_paths += self.traverse(child, path[:])

            if node == self.root and not child_paths:
                return [(self.root, "")]

            return child_paths

    @lmql.query
    async def final_result(self, reasoning):
        '''lmql
        sample()
            "{self.answer.callback_prompt.prefix}"
            "{reasoning}"
            "{self.answer.callback_prompt.suffix}"
            "[result]"
            if self.answer.callback_fn:
                return self.answer.callback_fn(result)
            return result
        from
            "openai/gpt-3.5-turbo"
        '''

    async def validate_result(self, result):
        if self.answer.validation.items:
            validation_failures = []
            for validation in self.answer.validation.items:
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
            "( yes/no )\n"
            "{self.answer.validation.prefix}"
            "{validation}"
            "{self.answer.validation.suffix}"
            "[yn]"
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

    # TODO: add continuation prompt (e.g. This next step is very important, so I am paying very close attention...)
    @lmql.query
    async def get_next_thought(self, reasoning):
        '''lmql
        sample(cache=False)
            "{reasoning}\n"
            "[thought]"
            return thought
        from 
            "openai/gpt-3.5-turbo"
        where 
            STOPS_BEFORE(thought, "\\n") and 
            STOPS_BEFORE(thought, "\n")
        '''

    @lmql.query
    async def is_finished(self, reasoning):
        '''lmql
        argmax
            "(yes/no)\n"
            "{self.reasoning.stopping.prefix}"
            "{reasoning}"
            "{self.reasoning.stopping.suffix}"
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
        fatal_flags = [self.bool_classify(self.reasoning.fatal.prefix, self.reasoning.fatal.suffix, statement, reasoning, should_be=False) for statement in self.reasoning.fatal.items]
        fatal_flags += [self.bool_classify(self.reasoning.vital.prefix, self.reasoning.vital.suffix, statement, reasoning, should_be=True) for statement in self.reasoning.vital.items]
        fatal_flags = await asyncio.gather(*fatal_flags)
        fatal_flags = [x[0] for x in fatal_flags]
        if any(fatal_flags):
            self.verbose_buffer += str(fatal_flags) + "\n"
            return 0

        evaluations = [self.grade(statement, reasoning) for statement in self.reasoning.graded.items]
        evaluations = await asyncio.gather(*evaluations)
        evaluations = [x[0] for x in evaluations]
        # self.verbose_buffer += "  " + str(evaluations)
        # self.verbose_buffer += f"  scored {sum(evaluations)}\n"
        return sum(evaluations)

    @lmql.query
    async def bool_classify(self, prefix, suffix, statement, reasoning, should_be=True):
        '''lmql
        argmax
            default = "yes" if should_be else "no"
            "( Answer yes/no. If not applicable, default to {default}. )\n"
            "{prefix}"
            "{reasoning}"
            "{suffix}"
            "{statement}: [yn]"
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
            "( rate each point from 1 - 9 where 5 is neutral. If N/A choose 5. )\n"
            "{self.reasoning.graded.prefix}"
            "{reasoning}"
            "{self.reasoning.graded.suffix}"
            "{statement}: [rating]"
            if rating[-1] in ["1", "2", "3", "4", "5", "6", "7", "8", "9"]:
                rating = int(rating[-1])
                rating = rating - 5
            else:
                rating = 0 # no information if improperly answered

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
