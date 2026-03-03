# [SARON] Script to generate 10K+ dummy records for testing (FR-1, Database Init)
import sqlite3
import random
from faker import Faker
import os

# Initialize Faker (optional for names/text, though we largely use defined lists here)
fake = Faker()

# Define constants
# Use an absolute path derived from this file's location so the script works
# regardless of which directory it is invoked from (consistent with backend/database.py)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'data', 'health_data.db')
NUM_RECORDS = 10000

# Ethiopian Regions for realism based on the project context
REGIONS = [
    "Addis Ababa", "Afar", "Amhara", "Benishangul-Gumuz", "Dire Dawa", 
    "Gambela", "Harari", "Oromia", "Sidama", "Somali", 
    "South West Ethiopia Peoples' Region", 
    "Southern Nations, Nationalities, and Peoples' Region (SNNPR)", "Tigray"
]

# Common diseases to track for health analytics
DISEASES = [
    "Malaria", "Diabetes", "Cholera", "Tuberculosis", "COVID-19", 
    "Measles", "Typhoid", "HIV/AIDS", "Hypertension", "Asthma"
]

# Common vaccines for public health records
VACCINES = [
    "Polio", "Measles", "BCG", "Pentavalent", "COVID-19", 
    "Yellow Fever", "Hepatitis B", "Rotavirus", "Pneumococcal", "HPV"
]

def create_tables(cursor):
    """
    Creates the 4 required structured health-related tables defined in the schema.
    This fulfills FR-1: System must connect to 4 structured health-related tables.
    
    Args:
        cursor (sqlite3.Cursor): The database cursor object used to execute SQLite commands.
    """
    print("Creating tables...")
    
    # Table 1: population_stats
    # Tracks demographic data across regions and years
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS population_stats (
        population_id INTEGER PRIMARY KEY AUTOINCREMENT,
        region VARCHAR(100),
        year INTEGER,
        total_population INTEGER,
        male_population INTEGER,
        female_population INTEGER
    )
    ''')

    # Table 2: disease_statistics
    # Tracks specific disease outbreaks, mortality, and recovery rates
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS disease_statistics (
        disease_id INTEGER PRIMARY KEY AUTOINCREMENT,
        disease_name VARCHAR(100),
        region VARCHAR(100),
        year INTEGER,
        total_cases INTEGER,
        total_deaths INTEGER,
        recovery_rate FLOAT
    )
    ''')

    # Table 3: hospital_resources
    # Tracks healthcare infrastructure capacity
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS hospital_resources (
        hospital_id INTEGER PRIMARY KEY AUTOINCREMENT,
        region VARCHAR(100),
        year INTEGER,
        number_of_hospitals INTEGER,
        available_beds INTEGER,
        doctors_count INTEGER,
        nurses_count INTEGER
    )
    ''')

    # Table 4: vaccination_records
    # Tracks immunization coverage
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS vaccination_records (
        vaccine_id INTEGER PRIMARY KEY AUTOINCREMENT,
        vaccine_name VARCHAR(100),
        region VARCHAR(100),
        year INTEGER,
        vaccinated_population INTEGER,
        coverage_percentage FLOAT
    )
    ''')

def generate_data(cursor):
    """
    Generates over 10,000 realistic dummy records and inserts them into the database.
    This provides the necessary scale to test the system's performance and query generation.
    
    Args:
        cursor (sqlite3.Cursor): The database cursor to execute INSERT statements.
    """
    print(f"Generating random data ({NUM_RECORDS} base iterations)...")

    # We will spread records across years 2010 to 2024 to allow for historical trend analysis
    years = list(range(2010, 2025))

    # 1. Populate population_stats 
    # Generates roughly 1 record per region per year (13 regions * 15 years = 195 records)
    for region in REGIONS:
        for year in years:
            total_pop = random.randint(100000, 50000000)
            # Roughly 50/50 split between male and female, with slight random variation
            male_ratio = random.uniform(0.48, 0.52)
            male_pop = int(total_pop * male_ratio)
            female_pop = total_pop - male_pop
            
            cursor.execute('''
                INSERT INTO population_stats (region, year, total_population, male_population, female_population)
                VALUES (?, ?, ?, ?, ?)
            ''', (region, year, total_pop, male_pop, female_pop))

    # 2. Populate disease_statistics
    # Generates a bulk of specific disease reports per year and region
    for _ in range(NUM_RECORDS // 4):
        disease = random.choice(DISEASES)
        region = random.choice(REGIONS)
        year = random.choice(years)
        
        # Base reported cases on a random scale
        total_cases = random.randint(10, 500000)
        # Deaths should logically be a fraction of total cases (0.1% to 15% mortality)
        total_deaths = int(total_cases * random.uniform(0.001, 0.15)) 
        # Recovery rate between 50% and 99.9%
        recovery_rate = round(random.uniform(50.0, 99.9), 2)

        cursor.execute('''
            INSERT INTO disease_statistics (disease_name, region, year, total_cases, total_deaths, recovery_rate)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (disease, region, year, total_cases, total_deaths, recovery_rate))

    # 3. Populate hospital_resources
    # Represents capacity at district levels or updates across the year
    for _ in range(NUM_RECORDS // 4):
        region = random.choice(REGIONS)
        year = random.choice(years)
        num_hospitals = random.randint(1, 100)
        
        # Estimation models: beds depend on hospital count, staff depends on beds/hospitals
        available_beds = num_hospitals * random.randint(50, 500)
        doctors = random.randint(num_hospitals * 2, num_hospitals * 20)
        nurses = random.randint(doctors * 2, doctors * 5)

        cursor.execute('''
            INSERT INTO hospital_resources (region, year, number_of_hospitals, available_beds, doctors_count, nurses_count)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (region, year, num_hospitals, available_beds, doctors, nurses))

    # 4. Populate vaccination_records
    # Build a cache of {(region, year): total_population} from the already-inserted
    # population_stats rows. This avoids 2,500 individual SELECT queries inside the loop.
    cursor.execute('SELECT region, year, total_population FROM population_stats')
    population_cache = {
        (row[0], row[1]): row[2] for row in cursor.fetchall()
    }

    for _ in range(NUM_RECORDS // 4):
        vaccine = random.choice(VACCINES)
        region = random.choice(REGIONS)
        year = random.choice(years)
        
        # Look up population from the cache instead of hitting the DB each iteration
        pop = population_cache.get((region, year))
        
        if pop is not None:
            vaccinated = random.randint(0, pop)
            coverage = round((vaccinated / pop) * 100, 2)
        else:
            # Fallback block (safety net if population record is somehow missing)
            vaccinated = random.randint(1000, 5000000)
            coverage = round(random.uniform(10.0, 99.9), 2)

        cursor.execute('''
            INSERT INTO vaccination_records (vaccine_name, region, year, vaccinated_population, coverage_percentage)
            VALUES (?, ?, ?, ?, ?)
        ''', (vaccine, region, year, vaccinated, coverage))

def main():
    """
    Main execution flow:
    1. Ensures the target directory for the db exists.
    2. Opens a connection to SQLite (creates actual .db file).
    3. Triggers table creation logic.
    4. Checks if database is empty to prevent duplicating 10k records on rerun.
    5. Seeds the DB and commits transactions.
    """
    # Ensure data directory path naturally exists so sqlite3 doesn't throw IO errors
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    # Connect to SQLite database. In SQLite, this will automatically create the file
    # 'data/health_data.db' if it does not yet exist.
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Step A: Instantiate the schema
    create_tables(cursor)
    
    # Step B: Check ALL 4 tables to detect a partial/interrupted seed run.
    # Only checking one table could leave the DB in an inconsistent state if a
    # previous run was interrupted after populating some tables but not others.
    tables_to_check = [
        "population_stats",
        "disease_statistics",
        "hospital_resources",
        "vaccination_records"
    ]
    
    counts = {}
    for table in tables_to_check:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        counts[table] = cursor.fetchone()[0]
    
    all_populated = all(count > 0 for count in counts.values())
    any_populated = any(count > 0 for count in counts.values())
    
    if all_populated:
        # All 4 tables have data — safe to skip
        print("Database already contains data in all tables. Skipping generation.")
        for table, count in counts.items():
            print(f"  - {table}: {count} records")
    else:
        if any_populated:
            # Partial seed detected — warn and re-seed to fix inconsistency
            print("WARNING: Partial seed detected. Some tables are empty. Re-seeding all tables...")
            for table, count in counts.items():
                status = f"{count} records" if count > 0 else "EMPTY"
                print(f"  - {table}: {status}")
        else:
            print("Database is empty. Seeding all tables...")

        generate_data(cursor)
        conn.commit()  # Save the insertions to disk
        print("Data seeded successfully!")

    # Always properly close the connection to avoid DB locks
    conn.close()

if __name__ == "__main__":
    main()

