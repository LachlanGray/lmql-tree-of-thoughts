from tree_of_thoughts import TreeOfThoughts


graded_criteria = [
    "The reasoning is reliable and repeatable",
    "We are getting closer to the answer"
    "It's impossible that there is a mistake",
    "The reasoning is clear and easy to follow",
]

vital_criteria = [
    "There is not a single math mistake in the reasoning",
]

fatal_criteria = [
    "The most recent step contains an error",
]

validations = [
    ("Does the expression utilize 4 operands?", True),
    ("Does the expression evaluate to 24?",  True)
]

callback_prompt = "using spaces between numbers and operators and obeying PEDMAS, the final expression is written as: "
callback_fn = lambda x: x.strip()

twenty_four_generator = TreeOfThoughts(
    graded_criteria,
    vital_criteria,
    fatal_criteria,
    validations=validations,
    callback_prompt=callback_prompt,
    callback_fn=callback_fn,
)

question = "Use 4 numbers and basic arithmetic operations (+-*/) to obtain 24. Only choose one number each step."

answers = twenty_four_generator.reason(question, verbose=True, print_tree=True)

print()
print("FINAL ANSWERS")
if answers:
    for answer in answers:
        print(answer)
        print()
else:
    print("Answer not found in max steps")




