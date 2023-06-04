from tree_of_thoughts import TreeOfThoughts

solver = TreeOfThoughts()
question = "Use 4 numbers and basic arithmetic operations (+-*/) to obtain 24"

final_answer = solver.reason(question, verbose=True, print_tree=True)

print()
print("FINAL ANSWERS")
if final_answer:
    for answer in final_answer:
        print(answer)
        print()
else:
    print("Answer not found in max steps")




