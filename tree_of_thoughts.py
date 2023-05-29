import lmql


class TreeOfThoughts:
    def __init__(self):
        self.tree = {}

    async def reason(self, question):
        root = question + " Let's think step by step:\n"
        self.tree = {root: []}
        thoughts = await self.get_next_thoughts(root)
        self.tree[root] = [res.variables["thought"] for res in thoughts]

        limit = 5
        current = 0

        while current < limit:
            # TODO: on each iteration append threads to a list of jobs and execute them in parallel
            for terminal, reasoning in self.traverse():
                if not await self.is_factual(reasoning):
                    del self.tree[terminal]

                if await self.can_answer(reasoning):
                    answer = await self.final_answer(reasoning)
                    final_reasoning = reasoning + "\n" + answer.variables["answer"]
                    if await self.is_factual(final_reasoning):
                        return answer

                thoughts = await self.get_next_thoughts(reasoning)
                self.tree[reasoning] = [res.variables["thought"] for res in thoughts]

            current += 1


    def traverse(self, root, path=None):
        '''
        returns all of the paths from the root to the leaves of the tree
        as a list of (terminal, reasoning)
        '''
        if path is None:
            path = []

        path.append(root)

        # If the current node is a leaf node, return its path
        if root not in self.tree or not self.tree[root]:
            return [(root, '\n    - '.join(path))]

        paths = []
        # If the current node has children, call the method recursively for each child
        for child in self.tree[root]:
            paths.extend(self.traverse(child, path.copy()))

        return paths

    @lmql.query
    async def final_answer(self, reasoning):
        '''lmql
        argmax
            "{reasoning}"
            "Therefore, [answer]"
        from
            openai/text-ada-001
        where
            STOPS_AT(answer, ".")
        '''

    @lmql.query
    async def get_next_thoughts(self, reasoning):
        '''lmql
        sample(n=3, temperature=0.8)
            "{reasoning}"
            "    - [thought]"
        from 
            openai/text-ada-001
        where 
            STOPS_AT(thought, ".")
        '''

    @lmql.query
    async def can_answer(self, reasoning):
        '''lmql
        argmax
            "{reasoning}"
            "[continue]"
            if continue == "Therefore":
                return True
            else:
                return False
        from 
            openai/text-ada-001
        where
            continue in {"Therefore", "    - "}
        '''

    @lmql.query
    async def is_factual(self, reasoning):
        '''lmql
        argmax
            "Think carefully: is there anything wrong with the following reasoning? yes or no\n\n"
            "```"
            "{reasoning}"
            "```\n"
            "[YN]"
            if YN == "yes":
                return False
            else:
                return True
        from 
            openai/text-ada-001
        where
            YN in {"yes", "no"}
        '''
