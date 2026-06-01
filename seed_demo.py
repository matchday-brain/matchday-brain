from app import seed_demo_data

if __name__ == "__main__":
    stats = seed_demo_data(clear=True)
    print("World Cup demo data loaded:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
