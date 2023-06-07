from tree_of_thoughts import TreeOfThoughts


graded_criteria = [
    "The actual meaning of question was perfectly understood",
    "The reasoning is reliable and repeatable",
    "It's impossible that there is a mistake",
    "The reasoning is clear and easy to follow",
]

vital_criteria = [
    "There is not a single math mistake in the reasoning",
]

fatal_criteria = [
    "The most recent step contains an error",
]

twenty_four_generator = TreeOfThoughts(graded_criteria, vital_criteria, fatal_criteria)

question = "Use 4 numbers and basic arithmetic operations (+-*/) to obtain 24. Go one number at a time."

answers = twenty_four_generator.reason(question, verbose=True, print_tree=True)

print()
print("FINAL ANSWERS")
if answers:
    for answer in answers:
        print(answer)
        print()
else:
    print("Answer not found in max steps")




