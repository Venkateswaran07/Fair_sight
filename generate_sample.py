import pandas as pd
import numpy as np

np.random.seed(42)
n = 1000

# 1. Base demographics
gender = np.random.choice(['Male', 'Female'], p=[0.6, 0.4], size=n)
age_group = np.random.choice(['Under 30', '30-45', 'Over 45'], size=n)

# 2. Base metrics
experience = np.random.normal(loc=5, scale=2, size=n)
interview_score = np.random.normal(loc=70, scale=10, size=n)

# 3. Create a Proxy attribute (Zip Code secretly correlates heavily with Gender)
zip_code = np.where(
    gender == 'Female', 
    np.random.choice(['10001', '10002'], size=n), 
    np.random.choice(['90210', '90211'], size=n)
)

# 4. Ground Truth (Who SHOULD get the job, based strictly on merit)
merit_score = (experience * 5) + (interview_score * 0.5)
ground_truth = (merit_score > np.median(merit_score)).astype(int)

# 5. The AI's Prediction (Heavily biased against Females)
# We add a hidden penalty to females to simulate a biased AI model
ai_penalty = np.where(gender == 'Female', -15, +5)
biased_score = merit_score + ai_penalty

# If biased score is above median, AI predicts 1 (Hired), else 0 (Rejected)
prediction = (biased_score > np.median(biased_score)).astype(int)

# Create final dataframe
df = pd.DataFrame({
    'applicant_id': [f"APP-{str(i).zfill(4)}" for i in range(1, n + 1)],
    'gender': gender,
    'age_group': age_group,
    'zip_code': zip_code,
    'years_experience': experience.round(1),
    'interview_score': interview_score.round(1),
    'ground_truth': ground_truth,
    'prediction': prediction
})

# Save to CSV
file_path = 'sample_biased_hiring_data.csv'
df.to_csv(file_path, index=False)
print(f"Success! Created {file_path} with {n} rows.")
