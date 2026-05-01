import statistics

scores = {
    "Alice": 92,
    "Bob": 78,
    "Carol": 85,
    "David": 61,
    "Eva": 95,
    "Frank": 73,
    "Grace": 88,
    "Henry": 54,
    "Isla": 79,
    "Jake": 67,
    "Karen": 91,
    "Leo": 83,
    "Raj": 99,
}

values = list(scores.values())

print("=== Test Score Analysis ===\n")

print("Individual Scores:")
for name, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
    print(f"  {name:<8} {score}")

print(f"\nClass Size:  {len(values)}")
print(f"Mean:        {statistics.mean(values):.1f}")
print(f"Median:      {statistics.median(values):.1f}")
print(f"Std Dev:     {statistics.stdev(values):.1f}")
print(f"Highest:     {max(values)} ({max(scores, key=scores.get)})")
print(f"Lowest:      {min(values)} ({min(scores, key=scores.get)})")

def letter_grade(score):
    if score >= 90: return "A"
    if score >= 80: return "B"
    if score >= 70: return "C"
    if score >= 60: return "D"
    return "F"

grade_counts = {}
for score in values:
    grade = letter_grade(score)
    grade_counts[grade] = grade_counts.get(grade, 0) + 1

print("\nGrade Distribution:")
for grade in ["A", "B", "C", "D", "F"]:
    count = grade_counts.get(grade, 0)
    bar = "#" * count
    print(f"  {grade}: {bar} ({count})")

passing = sum(1 for s in values if s >= 60)
print(f"\nPassing (>=60): {passing}/{len(values)} ({passing/len(values)*100:.0f}%)")
print(f"Above Average:  {sum(1 for s in values if s > statistics.mean(values))}/{len(values)}")
