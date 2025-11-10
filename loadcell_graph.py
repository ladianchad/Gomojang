import pandas as pd
import matplotlib.pyplot as plt
import glob # Used to find files easily

# -----------------------------------------------------------------
# 1. Settings
# -----------------------------------------------------------------

# 1. ★Must be identical★ to the one in your original script
BASE_CSV_FILENAME = 'loadcell_test1' 

# 2. File pattern to search for (e.g., 'loadcell_test1_*.csv')
FILE_PATTERN = f"{BASE_CSV_FILENAME}_*.csv"

# -----------------------------------------------------------------
# 2. Check for Library Installation
# -----------------------------------------------------------------
try:
    import pandas as pd
    import matplotlib.pyplot as plt
except ImportError:
    print("---!! Important !! ---")
    print("To draw graphs, you need the 'pandas' and 'matplotlib' libraries.")
    print("Please run the following command in your terminal:")
    print("pip install pandas matplotlib")
    print("---------------")
    exit()

# -----------------------------------------------------------------
# 3. Graphing Function
# -----------------------------------------------------------------

def plot_all_csv_files(pattern):
    """
    Finds all CSV files matching the pattern and plots them on one large figure.
    """
    
    # 1. Find the list of files matching the pattern
    csv_files = sorted(glob.glob(pattern)) # Sort to avoid mixed-up order (_100g, _200g, _none)
    
    if not csv_files:
        print(f"Error: Could not find any CSV files matching the pattern '{pattern}'.")
        print(f"1. Check if the '{BASE_CSV_FILENAME}' variable is correct.")
        print("2. Check if this script is in the same folder as the CSV files.")
        return

    print(f"Found files: {csv_files}")

    # 2. Prepare the figure for graphing (2x2 grid)
    # Assumes 4 files, creating a 2x2 grid.
    # If there are 3 files, it will draw 3 and leave the last one blank.
    fig, axes = plt.subplots(nrows=2, ncols=2, figsize=(15, 10))
    
    # Flatten the axes array from 2D to 1D (easier to loop)
    axes = axes.flatten() 

    # 3. Loop through each file and draw the graph
    for i, file_path in enumerate(csv_files):
        if i >= len(axes):
            print(f"Warning: File {file_path} will not be plotted as the 2x2 grid is full.")
            break
            
        ax = axes[i] # Select the current subplot to draw on

        try:
            # 4. Read the CSV file (parsing 'Timestamp' column as datetime objects)
            data = pd.read_csv(file_path, parse_dates=['Timestamp'])
            
            if data.empty:
                print(f"File {file_path} is empty. Skipping.")
                continue

            # 5. Plot the data
            # Original (Calibrated) data
            ax.plot(data['Timestamp'], data['CalibratedValue_g'], 
                    label='Calibrated (Raw)', 
                    alpha=0.6, linestyle='--')
            
            # Filtered data
            ax.plot(data['Timestamp'], data['FilteredValue_g'], 
                    label='Filtered (MVG Avg)', 
                    linewidth=2)

            # 6. Customize the plot
            ax.set_title(file_path, fontsize=12)
            ax.set_xlabel("Time")
            ax.set_ylabel("Weight (g)")
            ax.legend()
            ax.grid(True, which='both', linestyle='--', linewidth=0.5)
            
            # Rotate x-axis time labels by 45 degrees to prevent overlap
            ax.tick_params(axis='x', rotation=45)

        except Exception as e:
            print(f"An error occurred while processing {file_path}: {e}")
            
    # 7. Hide any unused subplots
    # (e.g., if there are 3 files, the 4th subplot will be empty and hidden)
    for j in range(len(csv_files), len(axes)):
        axes[j].axis('off')

    # 8. Set up the overall figure and show it
    plt.suptitle("Load Cell Data Analysis", fontsize=16, y=1.02)
    plt.tight_layout() # Automatically adjusts plots to prevent overlap
    
    # 9. Save and show the graph
    output_filename = f"{BASE_CSV_FILENAME}_analysis.png"
    plt.savefig(output_filename)
    print(f"--- Graph saved to {output_filename} ---")
    
    plt.show()

# -----------------------------------------------------------------
# 4. Run the Main Script
# -----------------------------------------------------------------
if __name__ == "__main__":
    plot_all_csv_files(FILE_PATTERN)
