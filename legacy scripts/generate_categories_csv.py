
import csv
import os

def generate_categories_csv(input_path: str, output_path: str):
    """
    Reads rules.csv and extracts unique category/subcategory pairs.
    Writes them to categories.csv.
    """
    if not os.path.exists(input_path):
        print(f"Input file not found: {input_path}")
        return

    unique_pairs = set()

    # Read rules
    with open(input_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cat = row.get('category', '').strip()
            sub = row.get('subcategory', '').strip()
            if cat: # Only if category is present. Subcategory can be empty.
                unique_pairs.add((cat, sub))

    # Write categories
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['category', 'subcategory'])
        for cat, sub in sorted(unique_pairs):
            writer.writerow([cat, sub])
    
    print(f"Generated {output_path} with {len(unique_pairs)} entries.")

if __name__ == "__main__":
    generate_categories_csv('data/rules.csv', 'data/categories.csv')
