from collections import defaultdict
from db import get_db_connection
import pandas as pd
from sklearn.linear_model import LinearRegression
import statistics

def analyze_player_performance(user_id, start_date=None, end_date=None):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetching PlayerID using UserID
    cursor.execute("SELECT PlayerID FROM Player WHERE UserID = %s", (user_id,))
    player_data = cursor.fetchone()
    if not player_data:
        print(f"No Player found for UserID {user_id}")
        return [], {}, {}

    player_id = player_data[0]

    # Fetching average scores grouped by course and hole
    query = """
        SELECT c.Name, h.HoleID, h.Par, AVG(ps.Score) AS avg_score
        FROM Player_has_Score ps
        JOIN Hole h ON ps.HoleID = h.HoleID
        JOIN Course c ON ps.CourseID = c.CourseID
        WHERE ps.PlayerID = %s
    """
    params = [player_id]

    # Apply date range filter if provided
    if start_date and end_date:
        query += " AND ps.ScoreDate BETWEEN %s AND %s"
        params.extend([start_date, end_date])

    query += " GROUP BY c.Name, h.HoleID, h.Par ORDER BY c.Name, h.HoleID"
    cursor.execute(query, tuple(params))

    results = cursor.fetchall()

    # Structure data for average scores by course
    avg_scores = {}
    for course_name, hole_id, par, avg_score in results:
        if course_name not in avg_scores:
            avg_scores[course_name] = []
        avg_scores[course_name].append({
            "hole_id": hole_id,
            "par": par,
            "avg_score": round(float(avg_score), 1)
        })

    # Fetching weak holes (holes with average scores greater than par)
    weak_query = """
        SELECT c.Name, h.HoleID, h.Par, AVG(ps.Score) AS avg_score
        FROM Player_has_Score ps
        JOIN Hole h ON ps.HoleID = h.HoleID
        JOIN Course c ON ps.CourseID = c.CourseID
        WHERE ps.PlayerID = %s
    """
    weak_params = [player_id]

    if start_date and end_date:
        weak_query += " AND ps.ScoreDate BETWEEN %s AND %s"
        weak_params.extend([start_date, end_date])

    weak_query += " GROUP BY c.Name, h.HoleID, h.Par HAVING avg_score > h.Par ORDER BY c.Name, h.HoleID"
    cursor.execute(weak_query, tuple(weak_params))

    weak_results = cursor.fetchall()

    # Structure data for weak holes
    weak_holes = {}
    for course_name, hole_id, par, avg_score in weak_results:
        if course_name not in weak_holes:
            weak_holes[course_name] = []
        weak_holes[course_name].append({
            "hole_id": hole_id,
            "par": par,
            "avg_score": round(float(avg_score), 1)
        })

    # Generate drill recommendations based on weak holes
    drills = generate_drill_recommendations(weak_holes)

    cursor.close()
    conn.close()

    # Convert avg_scores from dict to a list of dictionaries for easier handling in the template
    avg_scores_list = [{"course": course, "holes": holes} for course, holes in avg_scores.items()]

    return avg_scores_list, weak_holes, drills 

def generate_drill_recommendations(weak_holes):
    drills = {}
    for course, holes in weak_holes.items():
        drills[course] = []
        for hole in holes:
            if hole['par'] == 5:
                drills[course].append(f"Practice long drives for hole {hole['hole_id']}")
            elif hole['par'] == 4:
                drills[course].append(f"Focus on approach shots for hole {hole['hole_id']}")
            elif hole['par'] == 3:
                drills[course].append(f"Improve accuracy on short par-3 holes {hole['hole_id']}")
    return drills


def generate_predictions(player_id, course_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get the course name
    cursor.execute("SELECT Name FROM Course WHERE CourseID = %s", (course_id,))
    course_name = cursor.fetchone()[0]

    # Fetch historical data for training the model
    cursor.execute("""
        SELECT h.HoleID, h.Par, ps.Score
        FROM Player_has_Score ps
        JOIN Hole h ON ps.HoleID = h.HoleID
        WHERE ps.PlayerID = %s AND ps.CourseID = %s
    """, (player_id, course_id))
    data = cursor.fetchall()

    if not data:
        cursor.close()
        conn.close()
        return course_name, []

    df = pd.DataFrame(data, columns=['HoleID', 'Par', 'Score'])

    # Prepare the training data
    X = df[['HoleID', 'Par']]
    y = df['Score']

    # Train the model
    model = LinearRegression()
    model.fit(X, y)

    # Predict scores for the next round (unique holes only, no repetition)
    predictions = []
    unique_holes = df[['HoleID', 'Par']].drop_duplicates()  # Get unique holes only
    for _, row in unique_holes.iterrows():
        hole_id = row['HoleID']
        par = row['Par']
        predicted_score = model.predict([[hole_id, par]])[0]
        rounded_score = round(predicted_score)  # Round to nearest integer
        predictions.append((hole_id, par, rounded_score))

    cursor.close()
    conn.close()

    return course_name, predictions


    cursor.close()
    conn.close()

    return course_name, predictions