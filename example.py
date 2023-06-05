from tree_of_thoughts import TreeOfThoughts


graded_criteria = [
    "The most recent step is optimal",
    "The reasoning is addressing the question",
    "The chosen approach is working as intended",
    "The reasoning is converging towards an answer",
    "The reasoning is close to an answer",
]

vital_criteria = [
    "The most recent step is mathematically correct"
]

fatal_criteria = [
    "The most recent step makes a mathematical error"
]

twenty_four_generator = TreeOfThoughts(graded_criteria, vital_criteria, fatal_criteria)
question = "Use 4 numbers and basic arithmetic operations (+-*/) to obtain 24"

answers = twenty_four_generator.reason(question, verbose=True, print_tree=True)

print()
print("FINAL ANSWERS")
if answers:
    for answer in answers:
        print(answer)
        print()
else:
    print("Answer not found in max steps")




