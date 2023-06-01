from tree_of_thoughts import TreeOfThoughts

solver = TreeOfThoughts()
# question = "Roger has 5 tennis balls. He buys 2 more cans of tennis balls. Each can has 3 tennis balls. How many tennis balls does he have now?"
# question = "The concert was scheduled to be on 06/01/1943, but was delayed by one day to today. What is the date 10 days ago in MM/DD/YYYY?"
question = "use 4 numbers and basic arithmetic operations (+-*/) to obtain 24"

final_answer = solver.reason(question, verbose=False)

for answer in final_answer:
    print(answer)
    print()




