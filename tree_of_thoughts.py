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


@lmql.query_class
class TreeOfThoughts:
    def __init__(self):
        self.tree = {}
        self.root = ""
        self.answers = []

    def reason(self, question, verbose=False, print_tree=False):
        return asyncio.run(self._reason(question, verbose, print_tree))

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
        strategy = await self.choose_strategy(question)
        strategy = strategy[0]

        root = question + ". To answer, please " + strategy + "\n\nPlease carry out these steps below *with no explanations*."
        if verbose:
            print("ROOT --------------------")
            print(root)
            print()


        self.tree = {root: []}
        self.root = root

        limit = 3
        current = 1
        answers = []
        while current <= limit:
            
            # Determine if any leafs are ready to be answered
            if verbose:
                print("CHECKING FOR ANSWERABLE THOUGHTS --------------------")
            leaf_thoughts = []
            reasoning_paths = []
            can_answer = []
            for leaf_thought, reasoning_path in self.traverse(root):
                leaf_thoughts.append(leaf_thought)
                reasoning_paths.append(reasoning_path)
                can_answer.append(self.can_answer(reasoning_path + "\n - " + leaf_thought))
            
            can_answer = await asyncio.gather(*can_answer)
            can_answer = [x[0] for x in can_answer]

            if verbose:
                print(f"  {sum(can_answer)} answerable thoughts found")
                print()

            # Generate next thoughts and/or answers
            if verbose:
                print("GENERATING NEXT THOUGHTS --------------------")

            next_thoughts_list = []
            answer_leafs = []
            n_thoughts = 0
            n_answers = 0
            for leaf_thought, reasoning_path, can_answer in zip(leaf_thoughts, reasoning_paths, can_answer):
                if can_answer:
                    next_thoughts_list.append(self.final_answer(reasoning_path + "\n - " + leaf_thought))
                    answer_leafs.append(leaf_thought)
                    n_answers += 1
                else:
                    next_thoughts_list.append(self.get_next_thoughts(3, reasoning_path + "\n - " + leaf_thought))
                    n_thoughts += 3

            next_thoughts_list = await asyncio.gather(*next_thoughts_list)
            next_thoughts_list = [x if isinstance(x[0], str) else [y[0] for y in x] for x in next_thoughts_list]

            if verbose:
                print(f"  {n_thoughts} new thoughts, {n_answers} possible answers generated")
                print()

            # Prune leafs with bad reasoning, save good ones to the tree
            if verbose:
                print("PRUNING AND CHECKING ANSWERS --------------------")
            logic_checks_list = []
            for leaf_thought, reasoning_path, next_thoughts in zip(leaf_thoughts, reasoning_paths, next_thoughts_list):
                logic_checks_list.append(asyncio.gather(*[self.is_factual(reasoning_path + "\n - " + leaf_thought + "\n - " + next_thought) for next_thought in next_thoughts]))

            logic_checks_list = await asyncio.gather(*logic_checks_list)
            if verbose:
                n_true = 0
                n_false = 0
                for logic_checks in logic_checks_list:
                    for logic_check in logic_checks:
                        if logic_check:
                            n_true += 1
                        else:
                            n_false += 1
                print(f"  {n_true} logic checks passed, {n_false} failed")

            for leaf_thought, next_thoughts, logic_checks in zip(leaf_thoughts, next_thoughts_list, logic_checks_list):
                if any(logic_checks):
                    self.tree[leaf_thought] = []
                else:
                    continue

                for next_thought, logic_check in zip(next_thoughts, logic_checks):
                    if logic_check:
                        self.tree[leaf_thought].append(next_thought)

            # Check if any answer leafs succeeded
            n_successful_answers = 0
            for answer_leaf in answer_leafs:
                if self.tree[answer_leaf]:
                    answers.append(self.tree[answer_leaf][0])
                    n_successful_answers += 1

            if verbose:
                print(f"  {n_successful_answers} successful answers found")
                print()

            current += 1

            if answers:
                if print_tree:
                    self.print_tree()
                return answers

        if verbose:
            print("NO ANSWERS FOUND --------------------")
            self.print_tree()

    def traverse(self, node, path=None):
        '''
        returns all of the paths from the root to the leaves of the tree
        as a list of (thought, reasoning)
        '''
        if not path:
            path = []

        if node not in self.tree:
            return [(node, "\n - ".join(path))]
        else:
            if node == self.root and not self.tree[node]:
                return [(node, node)]

            path.append(node)
            paths = []
            for child in self.tree[node]:
                # paths.append(self.traverse(child, path[:]))
                paths += self.traverse(child, path[:])

            return paths

    @lmql.query
    async def choose_strategy(self, question):
        '''lmql
        sample()
            "In one sentence, the most reliable steps to systematically answer the question \" " 
            "{question}\" "
            "step-by-step are to"
            "[strategy]"
            return strategy
        from
            "openai/gpt-3.5-turbo"
        where
            STOPS_AT(strategy, ".")
        '''

    @lmql.query
    async def final_answer(self, reasoning):
        '''lmql
        sample()
            "{reasoning}\n\n"
            "Therefore, [answer]"
            return answer
        from
            "openai/gpt-3.5-turbo"
        where
            STOPS_BEFORE(answer, "\\n") and
            STOPS_BEFORE(answer, "\n") and 
            STOPS_BEFORE(answer, ".")
        '''

    async def get_next_thoughts(self, n, reasoning):
        thoughts = [self.get_next_thought(reasoning) for _ in range(n)]
        return await asyncio.gather(*thoughts)

    @lmql.query
    async def get_next_thought(self, reasoning):
        '''lmql
        sample()
            "{reasoning}"
            " - [thought]"
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
            "Does an immediate and obvious no-brain conclusion follow from this? yes or no?\n"
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

    # @lmql.query
    # async def can_answer(self, reasoning):
    #     '''lmql
    #     argmax
    #         "Does an immediate and obvious no-brain conclusion follow from this? yes or no?"
    #         "```"
    #         "{reasoning}"
    #         "```\n\n"
    #         "[ready]"
    #         if ready in ["yes", "Yes"]:
    #             return True
    #         else:
    #             return False
    #     from 
    #         "openai/text-davinci-003"
    #     where
    #         ready in {"yes", "no", "Yes", "No"}
    #     '''

    # @lmql.query
    # async def can_answer(self, reasoning):
    #     '''lmql
    #     argmax
    #         "{reasoning}"
    #         "[proceed]"
    #         if proceed == "Therefore":
    #             return True
    #         else:
    #             return False
    #     from 
    #         "openai/text-davinci-003"
    #     where
    #         proceed in {"Therefore", " - "}
    #     '''

    @lmql.query
    async def is_factual(self, reasoning):
        '''lmql
        argmax
            "Does this line of reasoning hold, AND is it on track to satisfy the meaning of the question? yes or no?\n\n"
            "```"
            "{reasoning}"
            "```\n"
            "[yn]"
            if yn.split()[-1] in ["yes", "Yes"]:
                return False
            else:
                return True
        from 
            "openai/gpt-3.5-turbo"
        where
            STOPS_AT(yn, "yes") and
            STOPS_AT(yn, "no") and
            STOPS_AT(yn, "Yes") and
            STOPS_AT(yn, "No") and
            len(TOKENS(yn)) < 20
        '''

    # @lmql.query
    # async def is_factual(self, reasoning):
    #     '''lmql
    #     argmax
    #         "Think carefully: Is something wrong with this passage? yes or no?\n\n"
    #         "```"
    #         "{reasoning}"
    #         "```\n"
    #         "[yn]"
    #         if yn in ["yes", "Yes"]:
    #             return False
    #         else:
    #             return True
    #     from 
    #         "openai/text-davinci-003"
    #     where
    #         yn in {"yes", "no", "Yes", "No"}
    #     '''
