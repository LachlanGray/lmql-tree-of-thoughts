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

class Node:
    def __init__(self, id: int, value: int | float, parent_id: int | None):
        self.id = id
        self.value = value
        self.parent_id = parent_id

class Tree:
    def __init__(self):
        self.nodes = {}
        self.stack = {}
        self.answers = []
        self.id_counter = 0

    def push(self, value: str, score: int | float, parent: Node):
        # nodes have unique names, still determined by counter
        # viable_leaf_ids is instead "data" and has keys for each of the nodes
        self.id_counter += 1

        if parent.id not in self.nodes:
            raise ValueError(f"Parent node {parent.value} ({parent.id}) not in tree")

        self.nodes[self.id_counter] = Node(self.id_counter, value, parent.id)

        self.stack[self.id_counter] = score

    def add_root(self, value: str) -> Node:
        self.id_counter += 1
        root_node = Node(self.id_counter, value, None)
        self.nodes[self.id_counter] = root_node

        return root_node

    def mark_as_answer(self, id: int, root_id: int):
        self.answers.append((id, root_id))

    def leaves_pop_top(self, n: int) -> list[int]:
        # selected_leaf_ids = sorted(self.viable_leaf_ids, key=self.viable_leaf_ids.get, reverse=True)[:n]
        # selected_leaf_ids = sorted(self.viable_leaf_ids, reverse=True)[:n]
        selected_leaf_ids = []
        i = self.id_counter
        while len(selected_leaf_ids) < n and i > 0:
            if i in self.stack:
                selected_leaf_ids.append(i)
            i -= 1

        for leaf_id in selected_leaf_ids:
            if self.nodes[leaf_id].parent_id:
                del self.stack[leaf_id]

        return selected_leaf_ids

    def get_path(self, id: int) -> tuple[Node, str, dict]:
        if id not in self.nodes:
            raise ValueError(f"Node {id} not in tree")

        node_values = []
        leaf_node = self.nodes[id]
        current_node = self.nodes[id]

        while current_node is not None:
            node_values.append(current_node.value)
            if current_node.parent_id is not None:
                current_node = self.nodes[current_node.parent_id]
            else:
                current_node = None

        reasoning_path = node_values[1:]
        reasoning_path = "\n".join(reversed(reasoning_path))

        return leaf_node, reasoning_path, {}

    def paths_pop_top(self, n) -> list[tuple[Node, str, dict]]:
        selected_leaf_ids = self.leaves_pop_top(n)
        return [self.get_path(id) for id in selected_leaf_ids]

class TreeOfThoughts:
    initial: PromptSandwich
    reasoning: ReasoningPrompt
    answer: AnswerPrompt

    def __init__(self, initial, reasoning, answer, max_iterations=10):

        self.initial = create_prompt_sandwich(initial)
        self.reasoning = create_prompt_reasoning(reasoning)
        self.answer = create_prompt_answer(answer)

        self.max_iterations = max_iterations

        self.penalties = [] # TODO: investigate if these are useful, would add into evaluations
        self.bonuses = []

        # self.params = {criteria: (1, 0) for criteria in self.graded_criteria} # TODO: use these in self.process_rating

        self.tree = Tree()

        # TODO: memory, error propagation

        self.verbose_buffer = ""

    def reason(self, argument, n_active_leaves, n_branches, verbose=False):
        return asyncio.run(self.async_reason(argument, n_active_leaves, n_branches, verbose))

    def print_verbose(self):
        # clear screen
        print("\033c", end="")
        print(self.verbose_buffer)

    async def async_reason(self, argument, n_active_leaves, n_branches, verbose=False):
        self.verbose_buffer = ""
        self.argument = argument

        root_value = self.initial.prefix + argument + self.initial.suffix
        root = self.tree.add_root(root_value)

        if verbose:
            self.verbose_buffer += color['cyan']( "ROOT ------------------------------------------------------\n")
            self.verbose_buffer += root_value + "\n\n"
            self.print_verbose()

        current = 1

        while current <= self.max_iterations:

            if verbose:
                self.verbose_buffer += color['green'](f"ITERATION {current}\n")
                self.verbose_buffer += color['cyan']( "CHECKING FOR ANSWERABLE THOUGHTS --------------------------\n")
                self.print_verbose()

            # get (node, path_string) pairs, and default to the root if all leaves die
            selected_leaves = self.tree.paths_pop_top(n_active_leaves)

            if selected_leaves:
                can_answer = await asyncio.gather(*[self.is_finished(path + "\n" + thought.value) for thought, path, attrs in selected_leaves])
                can_answer = [x[0] for x in can_answer]
                for i, is_answerable in enumerate(can_answer):
                    selected_leaves[i][2]["preceeds_answer"] = is_answerable
            else:
                selected_leaves = [(root, "", {"preceeds_answer": False})]

            if verbose:
                tally = sum(1 for _, _, meta in selected_leaves if meta.get('preceeds_answer', False))
                self.verbose_buffer += f"  {tally} selected leaves are potential answers\n\n"
                self.verbose_buffer += color['cyan']( "GENERATING NEXT THOUGHTS ----------------------------------\n")
                self.print_verbose()

            if verbose:
                self.verbose_buffer += color['cyan']("\n------------------------------\n").join([reasoning_path + "\n" + color['blue'](leaf_node.value) + "\n" for leaf_node, reasoning_path, attrs in selected_leaves]) + "\n"
                self.print_verbose()

            next_thoughts_list = []
            for leaf_thought, reasoning_path, attrs in selected_leaves:
                if attrs["preceeds_answer"]:
                    next_thoughts_list.append(self.final_result(reasoning_path + "\n" + leaf_thought.value))
                else:
                    next_thoughts_list.append(self.get_next_thoughts(n_branches, reasoning_path + "\n" + leaf_thought.value))

            next_thoughts_list = await asyncio.gather(*next_thoughts_list)
            next_thoughts_list = [x if isinstance(x[0], str) else [y[0] for y in x] for x in next_thoughts_list]

            if verbose:
                tally = sum(len(x) for x in next_thoughts_list)
                self.verbose_buffer += f"  {tally} new thoughts from here\n\n" 
                self.verbose_buffer += color['cyan']( "ASSESSING THOUGHT PATHS -----------------------------------\n")
                self.print_verbose()

            thought_scores_list = []
            for leaf_thought, next_thoughts in zip(selected_leaves, next_thoughts_list):
                leaf, reasoning_path, attrs = leaf_thought
                if attrs["preceeds_answer"]:
                    thought_scores_list.append(*[self.validate_result(next_thoughts[0])]) # attempted answers only have one branch
                else:
                    thought_scores_list.append(asyncio.gather(*[self.evaluate_reasoning(reasoning_path + "\n" + leaf.value + "\n" + next_thought) for next_thought in next_thoughts]))

            thought_scores_list = await asyncio.gather(*thought_scores_list)
            thought_scores_list = [x if isinstance(x, list) else [x] for x in thought_scores_list]

            if verbose:
                n_thoughts = sum(len(x) for x in thought_scores_list)
                n_true = sum([1 for x in thought_scores_list for num in x if num > 0])
                self.verbose_buffer += f"  {n_true}/{n_thoughts} of the new thoughts are viable\n"
                self.print_verbose()

            answers = []
            for leaf_thought, next_thoughts, next_thought_ratings in zip(selected_leaves, next_thoughts_list, thought_scores_list):
                leaf, reasoning_path, attrs = leaf_thought
                for next_thought, rating in sorted(zip(next_thoughts, next_thought_ratings), key=lambda x: x[1], reverse=True):
                    if rating > 0:
                        self.tree.push(next_thought, score=rating, parent=leaf)

            # for leaf_thought, next_thought_ratings in zip(selected_leaves, thought_scores_list):
                if leaf_thought[2]["preceeds_answer"] and next_thought_ratings[0] > 0:
                    answers.append(next_thoughts[0])
                    self.tree.mark_as_answer(leaf.id, root.id)

            if verbose:
                self.verbose_buffer += f"  {len(answers)} answers passing validation\n\n"
                self.print_verbose()

            current += 1

            if answers:
                return answers

        if verbose:
            self.verbose_buffer += color['cyan']( "NO ANSWERS FOUND IN MAX STEPS -----------------------------\n\n")
            self.print_verbose()

        return []

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
            loop = asyncio.get_event_loop()
            answer_validations = []
            for validation in self.answer.validation.items:
                if isinstance(validation, tuple):
                    answer_validations.append(self.prompt_validate(result, validation[0], validation[1]))
                else:
                    answer_validations.append(loop.run_in_executor(None, validation, result))
                    # answer_validations.append(validation(result))

            answer_validations = await asyncio.gather(*answer_validations)
            answer_validations = [x[0] if isinstance(x, list) else x for x in answer_validations]

            if not all(answer_validations):
                return 0 # below survival threshold

        return 1 # above survival threshold

    @lmql.query
    async def prompt_validate(self, result, validation, should_be):
        """lmql
        argmax
            "( yes/no )\n"
            "{self.answer.validation.prefix}"
            "{result}"
            "{self.answer.validation.suffix}"
            parsed_validation = validation.replace('$arg', self.argument)
            "{parsed_validation}"
            "[yn]"
            if yn.split()[-1]  in ["yes", "Yes"]:
                answer = True
            else:
                answer = False

            return answer == should_be
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
        sample()
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

    # TODO: programmatic constraints and evaluations
    # TODO: explore metaprompting for rating criteria
    async def evaluate_reasoning(self, reasoning):
        thought_validations = [self.validate_thought(self.reasoning.fatal.prefix, self.reasoning.fatal.suffix, statement, reasoning, should_be=False) for statement in self.reasoning.fatal.items]
        thought_validations += [self.validate_thought(self.reasoning.vital.prefix, self.reasoning.vital.suffix, statement, reasoning, should_be=True) for statement in self.reasoning.vital.items]
        thought_validations = await asyncio.gather(*thought_validations)
        thought_validations = [x[0] for x in thought_validations]
        if not all(thought_validations):
            return 0

        evaluations = [self.grade(statement, reasoning) for statement in self.reasoning.graded.items]
        evaluations = await asyncio.gather(*evaluations)
        evaluations = [x[0] for x in evaluations]
        return sum(evaluations)

    @lmql.query
    async def validate_thought(self, prefix, suffix, statement, reasoning, should_be=True):
        '''lmql
        argmax
            default = "yes" if should_be else "no"
            "( Answer yes/no. If not applicable, default to {default}. )\n"
            "{prefix}"
            "{reasoning}"
            "{suffix}"
            "{statement}: [yn]"
            if yn.split()[-1] in ["yes", "Yes"]:
                answer = True
            else:
                answer = False

            return answer == should_be
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
