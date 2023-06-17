from tree_of_thoughts import TreeOfThoughts

tree_config = {
    "initial": {
        "prefix": "Iterate through the word '",
        "suffix": "' letter by letter, and note the index of each letter.",
    },
    "reasoning": {
        "graded": {
            "items": [
                "On a scale of 1-9 the instructions are being respected so far: "
            ],
        },
    },
    "answer": {
        "callback_prompt": {
            "suffix": "\nThe total number of of 'n' occurences is: ",
        },
        "callback_fn": lambda x: x.replace(".", "").strip(),
        "validation" : {
            "items": [
                  lambda s: s.isdigit()
            ]
        },
    },
}

letter_n_counter = TreeOfThoughts(**tree_config, max_iterations=15)

answers = letter_n_counter.reason("mayonnaise", n_active_leaves=1, n_branches=1, verbose=True)

print()
print("FINAL ANSWERS")
print(answers)
