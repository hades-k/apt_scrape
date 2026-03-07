#!/usr/bin/env python3
"""
Process Milano listings JSON and create CSV with filtered results.
"""

import json
import csv
import re

def extract_price(price_str):
    """Extract numeric price from string like '€ 1.000/mese'"""
    match = re.search(r'(\d+(?:\.\d+)?)', price_str.replace('.', ''))
    return float(match.group(1)) if match else 0

def extract_sqm(sqm_str):
    """Extract numeric sqm from string like '65 m²'"""
    match = re.search(r'(\d+)', sqm_str)
    return int(match.group(1)) if match else 0

def check_heating(description):
    """Check if description mentions independent heating"""
    heating_keywords = ['riscaldamento autonomo', 'autonomo', 'riscaldamento indipendente']
    return any(keyword in description.lower() for keyword in heating_keywords)

def check_pets(description):
    """Check if description mentions pets allowed"""
    pet_keywords = ['animali', 'pet', 'cani', 'gatti', 'domestici']
    return any(keyword in description.lower() for keyword in pet_keywords)

def main():
    with open('milano_listings.json', 'r') as f:
        data = json.load(f)

    filtered_listings = []
    for listing in data['listings']:
        price = extract_price(listing['price'])
        sqm = extract_sqm(listing['sqm'])

        # Basic filters
        if price > 1000 or sqm < 50:
            continue

        # Check for heating and pets in description
        description = listing.get('description_snippet', '').lower()
        has_independent_heating = check_heating(description)
        pet_friendly = check_pets(description)

        # For now, include all that match basic criteria
        # User can manually check for heating/pets or we can filter
        filtered_listings.append({
            'title': listing['title'],
            'url': listing['url'],
            'price': price,
            'sqm': sqm,
            'rooms': listing['rooms'],
            'bathrooms': listing['bathrooms'],
            'has_independent_heating': has_independent_heating,
            'pet_friendly': pet_friendly,
            'features': ', '.join(listing.get('features_raw', [])),
            'description_snippet': listing.get('description_snippet', '')[:200] + '...'
        })

    # Write to CSV
    with open('milano_apartments.csv', 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['title', 'url', 'price', 'sqm', 'rooms', 'bathrooms',
                     'has_independent_heating', 'pet_friendly', 'features', 'description_snippet']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for listing in filtered_listings:
            writer.writerow(listing)

    print(f"Processed {len(filtered_listings)} listings and saved to milano_apartments.csv")

if __name__ == '__main__':
    main()