from tree_of_thoughts import TreeOfThoughts

# first: unpack this

tree_config = {
    "initial": {
        "prefix": "Question: use 4 numbers and basic arithmetic operations (+-*/) to obtain ",
        "suffix": ". Only choose one number each step.\nAnswer: Let's think step by step.",
    },
    "reasoning": {
        "graded": {
            "prefix": "Please assess the following reasoning, and choose an option for each point:\n```\n",
            "suffix": "\n```\n\n",
            "items": [
                "The reasoning is reliable and repeatable: ",
                "We are getting closer to the answer: "
                "It's impossible that there is a mistake: ",
                "The reasoning is clear and easy to follow: ",
            ],
        },
        "vital": {
            "prefix": "Please assess the following reasoning, and choose an option for each point:\n```\n",
            "suffix": "\n```\n",
            "items": [
                "There is not a single math mistake in the reasoning: ",
            ]
        },
        "fatal": {
            "prefix": "Please assess the following reasoning, and choose an option for each point.\n```\n",
            "suffix": "\n```\n",
            "items": [
                "There is a math mistake in the reasoning",
            ]
        },
        "stopping": {
            "prefix": "Has the following reasoning achieved a correct and satisfying answer to the initial question?\n```\n",
            "suffix": "\n```\n\nAnswer: ",
        },
    },
    "answer": {
        "callback_prompt": {
            "prefix": "Rewriting the expression `",
            "suffix": "` using spaces between numbers and operators and obeying PEDMAS, the final expression is written as: ",
        },
        "callback_fn": lambda x: x.strip(),
        "validation" : {
            "prefix": "I have a question about the expression `",
            "suffix": "`. ",
            "items": [
                ("Does the expression utilize 4 operands?", True),
                ("Does the expression evaluate to 24?",  True) # TODO: see if {argument} works
            ]
        },
    },
}

number_maker = TreeOfThoughts(**tree_config)

answers = number_maker.reason("24", verbose=True, print_tree=True)

print()
print("FINAL ANSWERS")
print(answers)
