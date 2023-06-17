from tree_of_thoughts import TreeOfThoughts

tree_config = {
    "initial": { # sandwiches the argument passed to self.reason
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
        # both vital and fatal are applied to the reasoning after each new thought is generated
        "vital": {
            "prefix": "Please assess the following reasoning, and choose an option for each point:\n```\n",
            "suffix": "\n```\n",
            "items": [ # if any of these questions are answered "no" the new leaf dies
                "There is not a single math mistake in the reasoning: ",
            ]
        },
        "fatal": { # if any of these questions are answered "yes" the new leaf dies
            "prefix": "Please assess the following reasoning, and choose an option for each point.\n```\n",
            "suffix": "\n```\n",
            "items": [
                "There is a math mistake in the reasoning: ",
            ]
        },
        "stopping": { # Applied at the start of each iteration to flag potential answers
            "prefix": "Has the following reasoning achieved a correct and satisfying answer to the initial question?\n```\n",
            "suffix": "\n```\n\nAnswer: ",
        },
    },
    "answer": {
        "callback_prompt": { # Applied to the reasoning leading up to an answer
            "suffix": "In conclusion, using (+,-,x,/) and obey PEDMAS, in one expression it is written as: ",
        },
        "callback_fn": lambda x: x.replace(".", "").strip(), # Applied to the result of whatever follows from the callback prompt
        "validation" : { # validations can be a yes no question and expected answer, or any bool returning function
            "prefix": "Please answer the following questions about the expression `",
            "suffix": "`. ",
            "items": [ # TODO: allow argument usage in all prompts and not just validation
                ("Are four numbers used to obtain $arg?", True), # $arg substitutes the reasoning argument into the validation prompt
                ("Does the expression really equal $arg?",  True)
            ]
        },
    },
}

number_maker = TreeOfThoughts(**tree_config)

# The top n_active_leafs scoring leafs are selected on each iteration
# n_branches new thoughts breanch from them if they are not answers
answers = number_maker.reason("24", n_active_leaves=2, n_branches=3, verbose=True)

print()
print("FINAL ANSWERS")
print(answers)
