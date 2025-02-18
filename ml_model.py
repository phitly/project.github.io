import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error
from db import get_db_connection

def fetch_training_data():
    conn = get_db_connection()
    query = """
        SELECT ps.Score, ps.HoleID, h.Par, c.CourseID, c.Name, ps.ScoreDate
        FROM Player_has_Score ps
        JOIN Hole h ON ps.HoleID = h.HoleID
        JOIN Course c ON ps.CourseID = c.CourseID
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def train_model():
    # Fetch and prepare the data
    data = fetch_training_data()
    data['ScoreDate'] = pd.to_datetime(data['ScoreDate'])
    
    # Feature engineering
    data['Course_Encoded'] = data['CourseID']
    
    features = ['HoleID', 'Par', 'Course_Encoded']
    target = 'Score'
    
    X = data[features]
    y = data[target]
    
    # Train-test split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Train the model
    model = LinearRegression()
    model.fit(X_train, y_train)
    
    # Make predictions and evaluate
    y_pred = model.predict(X_test)
    mse = mean_squared_error(y_test, y_pred)
    print(f"Model trained with MSE: {mse:.2f}")
    
    return model

def make_predictions(model, player_id, course_id):
    conn = get_db_connection()
    query = """
        SELECT h.HoleID, h.Par, c.CourseID
        FROM Hole h
        JOIN Course c ON h.CourseID = c.CourseID
        WHERE c.CourseID = %s
    """
    holes_data = pd.read_sql(query, conn, params=[course_id])
    conn.close()
    
    # Prepare data for prediction
    holes_data['Course_Encoded'] = holes_data['CourseID']
    features = ['HoleID', 'Par', 'Course_Encoded']
    predictions = model.predict(holes_data[features])
    
    holes_data['Predicted_Score'] = predictions
    return holes_data

if __name__ == "__main__":
    model = train_model()
    print("Model training completed!")