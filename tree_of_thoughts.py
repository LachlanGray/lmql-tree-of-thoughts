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
        self.answers = []

    def reason(self, question, verbose=False):
        return asyncio.run(self._reason(question, verbose))

    async def _reason(self, question, verbose):
        root = question + " Let's think one step at a time:"
        if verbose:
            print("\033c")
            print("QUESTION: " + question)
            print()

        self.tree = {root: []}
        # thoughts = await self.get_next_thoughts(root, 3)
        # self.tree[root] = [thought.variables["thought"] for thought in thoughts]

        limit = 4
        current = 1
        answers = []
        while current <= limit:
            new_thoughts = {}

            if verbose:
                print(color['blue'](f"ITERATION {current} ---------------------------"))
            for thought, reasoning in self.dfs(root):

                if thought == reasoning:
                    thoughts = await self.get_next_thoughts(3, reasoning)
                    new_thoughts[thought] = [thought[0].variables["thought"] for thought in thoughts]
                    continue

                continued_reasoning = reasoning + "\n -" + thought
                is_factual = await self.is_factual(continued_reasoning)

                if verbose:
                    print(reasoning)
                    print(f" -{color['cyan'](thought)}")
                    print()
                    print(color['green']('GOOD REASONING') if is_factual else color['red']('BAD REASONING'))
                    print()

                if not is_factual:
                    continue

                reasoning = continued_reasoning

                can_answer = await self.can_answer(reasoning)

                if can_answer:
                    answer = await self.final_answer(reasoning)
                    answer = answer[0].variables["answer"]
                    formatted_answer = "Therefore," + answer + "."

                    if verbose:
                        print(color['blue']('ATTEMPTING ANSWER: ')  + f"{color['cyan'](formatted_answer)}")

                    final_reasoning = reasoning + "\n\n" + formatted_answer
                    if await self.is_factual(final_reasoning):
                        if verbose:
                            print()
                            print(color['blue']("COMPLETE REASONING --------------------"))
                            print(final_reasoning)

                        new_thoughts[thought] = answer
                        answers.append(answer)

                if verbose:
                    print(color['blue']('- next thought -------------------'))

                thoughts = await self.get_next_thoughts(3, reasoning)
                new_thoughts[thought] = [thought[0].variables["thought"] for thought in thoughts]

            current += 1

            self.tree.update(new_thoughts)

            self.answers = answers

            if answers: 
                if verbose:
                    print(color['blue']("ANSWERS FOUND ---------------------"))
                break

        return answers


    def dfs(self, node, path=[]):
        '''
        returns all of the paths from the root to the leaves of the tree
        as a list of (thought, reasoning)
        '''
        if node not in self.tree:
            return (node, "\n -".join(path))
        else:
            if not self.tree[node]:
                return [(node, node)]

            path.append(node)
            paths = []
            for child in self.tree[node]:
                paths.append(self.dfs(child, path[:]))

            return paths

    @lmql.query
    async def final_answer(self, reasoning):
        '''lmql
        sample()
            "{reasoning}\n\n"
            "Therefore, [answer]"
        from
            "openai/gpt-3.5-turbo"
        where
            STOPS_BEFORE(answer, ".") and
            STOPS_BEFORE(answer, "\\n")
        '''

    async def get_next_thoughts(self, n, reasoning):
        tasks = [self.get_next_thought(reasoning) for _ in range(n)]
        results = await asyncio.gather(*tasks)
        return results

    @lmql.query
    async def get_next_thought(self, reasoning):
        '''lmql
        sample(temperature=0.8)
            "{reasoning}"
            " -[thought]"
        from 
            "openai/gpt-3.5-turbo"
        where 
            STOPS_BEFORE(thought, "\\n") and 
            STOPS_BEFORE(thought, ".")
        '''

    @lmql.query
    async def can_answer(self, reasoning):
        '''lmql
        argmax
            "Does an immediate and obvious no-brain conclusion follow from this? yes or no?"
            "```"
            "{reasoning}"
            "```\n\n"
            "[ready]"
            if ready in ["yes", "Yes"]:
                return True
            else:
                return False
        from 
            "openai/text-davinci-003"
        where
            yn in {"yes", "no", "Yes", "No"}
        '''

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
    #         proceed in {"Therefore", " -"}
    #     '''

    @lmql.query
    async def is_factual(self, reasoning):
        '''lmql
        argmax
            "Think carefully: Is something wrong with this passage? yes or no\n\n"
            "```"
            "{reasoning}"
            "```\n"
            "[yn]"
            if yn in ["yes", "Yes"]:
                return False
            else:
                return True
        from 
            "openai/text-davinci-003"
        where
            yn in {"yes", "no", "Yes", "No"}
        '''
