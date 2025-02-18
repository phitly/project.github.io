from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from analysis import analyze_player_performance  # Importing the analysis function
from analysis import generate_predictions
from db import get_db_connection
from ml_model import train_model, make_predictions
from jinja2 import Environment, select_autoescape
from datetime import datetime, timedelta
from ml_model import train_model, make_predictions
import joblib
import mysql.connector
import bcrypt
import secrets
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_wtf import FlaskForm
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging
from flask_wtf.csrf import generate_csrf
import os


# Flask app
app = Flask(__name__)

# Add rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Configure logging
logging.basicConfig(
    filename='golf_app.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)

try:
    model = joblib.load('golf_model.pkl')  
except FileNotFoundError:
    model = train_model()  
    import joblib
    joblib.dump(model, 'golf_model.pkl')  # Save the model
# Generate a random secret key
app.secret_key = secrets.token_urlsafe(32)  
print(f'Secret Key: {app.secret_key}')  

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Add CSRF error handler
@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    return render_template('csrf_error.html', reason=e.description), 400

# Update your forms to include CSRF token
@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf())

# Add this form class after your imports
class EmptyForm(FlaskForm):
    pass

# Database connection setup
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='new_password',
            database='mydb'
        )
        return conn
    except mysql.connector.Error as err:
        logging.error(f"Database connection error: {err}")
        raise

# Near the top of your file after app initialization
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # Optional: sets token timeout to 1 hour

# Home Route
@app.route('/')
def home():
    form = EmptyForm()
    if 'user_id' in session:
        user_id = session['user_id']

        # Initialize variables
        username = 'Unknown'
        player_name = 'Player not found'
        courses = []

        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Fetch the user's information
            cursor.execute("SELECT Username FROM User WHERE UserID = %s", (user_id,))
            user = cursor.fetchone()
            username = user[0] if user else username  # Default to 'Unknown' if no user found
            
            # Fetch the player's information linked to the user
            cursor.execute("SELECT Name FROM Player WHERE UserID = %s", (user_id,))
            player = cursor.fetchone()
            player_name = player[0] if player else player_name  # Default if no player found

            # Fetch the list of courses
            cursor.execute("SELECT CourseID, Name FROM Course")
            courses = cursor.fetchall()  # Fetch all courses
            
            if not courses:
                flash("No courses available. Please add courses.", "info")
        
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", 'danger')
        finally:
            cursor.close()
            conn.close()

        # Pass the fetched data to the template
        return render_template(
            'home.html',
            username=username,
            player_name=player_name,
            courses=courses,
            form=form
        )
    else:
        flash("You need to log in first.", "warning")
        return redirect(url_for('login'))

# User Registration
@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per minute")
def register():
    form = EmptyForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            username = request.form['username'].strip()
            password = request.form['password']
            player_name = request.form['player_name'].strip()

            # Input validation
            if not all([username, password, player_name]):
                flash("All fields are required.", "danger")
                return render_template('register.html', form=form)

            if len(password) < 8:
                flash("Password must be at least 8 characters long.", "danger")
                return render_template('register.html', form=form)

            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO User (Username, Password, role) VALUES (%s, %s, 'player')", 
                             (username, hashed_password))
                conn.commit()
                user_id = cursor.lastrowid

                cursor.execute("INSERT INTO Player (Name, UserID) VALUES (%s, %s)", 
                             (player_name, user_id))
                conn.commit()

                session['user_id'] = user_id
                session['username'] = username
                session['player_name'] = player_name
                session['role'] = 'player'

                logging.info(f"New user registered: {username}")
                flash('Registration successful! You are now logged in.', 'success')
                return redirect(url_for('home'))

            except mysql.connector.Error as err:
                logging.error(f"Database error during registration: {err}")
                flash(f"Error: {err}", 'danger')
            finally:
                cursor.close()
                conn.close()

    return render_template('register.html', form=form)

# User Login
@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    form = EmptyForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            username = request.form['username']
            password = request.form['password']

            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT UserID, Username, Password, role FROM User WHERE Username = %s", (username,))
                user_data = cursor.fetchone()

                if user_data and bcrypt.checkpw(password.encode('utf-8'), user_data[2].encode('utf-8')):
                    session['user_id'] = user_data[0]
                    session['username'] = user_data[1]
                    session['role'] = user_data[3]

                    cursor.execute("SELECT Name FROM Player WHERE UserID = %s", (session['user_id'],))
                    player_data = cursor.fetchone()
                    
                    if player_data:
                        session['player_name'] = player_data[0]
                    else:
                        session['player_name'] = "N/A"

                    logging.info(f"Successful login for user: {username}")
                    flash('Login successful!', 'success')
                    return redirect(url_for('home'))
                else:
                    logging.warning(f"Failed login attempt for user: {username}")
                    flash('Invalid credentials. Please try again.', 'danger')

            except mysql.connector.Error as err:
                logging.error(f"Database error during login: {err}")
                flash(f"Database error: {err}", 'danger')
            finally:
                cursor.close()
                conn.close()

    return render_template('login.html', form=form)

# Delete User Route
@app.route('/delete_user', methods=['POST'])
def delete_user():
    if 'user_id' in session:  # Check if user is logged in
        user_id = session['user_id']
        
        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Delete the user from the database
            cursor.execute("DELETE FROM User WHERE UserID = %s", (user_id,))
            conn.commit()
            flash('Your account has been deleted successfully.', 'success')
            session.pop('user_id', None)  # Log the user out after deletion
            return redirect(url_for('home'))  # Redirect to home or another page
        except mysql.connector.Error as err:
            flash(f"Error: {err}", 'danger')
        finally:
            cursor.close()
            conn.close()
    else:
        flash('You need to be logged in to delete your account.', 'danger')
    return redirect(url_for('home'))

#enter score
@app.route('/enter_score', methods=['GET', 'POST'])
def enter_score():
    form = EmptyForm()
    course_id = request.args.get('course_id')
    holes = request.args.get('holes')

    # Fetch hole data
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Validate course existence
        cursor.execute("SELECT CourseID FROM Course WHERE CourseID = %s", (course_id,))
        if not cursor.fetchone():
            flash('Invalid course selected.', 'danger')
            return redirect(url_for('home'))

        # Fetch holes data for the course
        cursor.execute("SELECT HoleID, Par FROM Hole WHERE CourseID = %s ORDER BY HoleID", (course_id,))
        holes_data = cursor.fetchall()
        if not holes_data:
            flash('No holes found for the selected course.', 'danger')
            return redirect(url_for('home'))

        # Limit to first 9 holes if needed
        if int(holes) == 9:
            holes_data = holes_data[:9]

        # Fetch PlayerID for the logged-in user
        cursor.execute("SELECT PlayerID FROM Player WHERE UserID = %s", (session['user_id'],))
        player_data = cursor.fetchone()
        if not player_data:
            flash('Player not found for the logged-in user.', 'danger')
            return redirect(url_for('home'))
        player_id = player_data[0]
    except mysql.connector.Error as err:
        flash(f"Error fetching course or player data: {err}", 'danger')
        return redirect(url_for('home'))
    finally:
        cursor.close()
        conn.close()

    if request.method == 'POST':
        # Capture the play_date from the form
        play_date = request.form.get('play_date')

        if not play_date:
            flash('Please select a date', 'danger')
            return redirect(url_for('enter_score', course_id=course_id, holes=holes))

        # Validate each score
        scores = []
        for hole in holes_data:
            score_key = f'score_{hole[0]}'  # Use HoleID to generate key
            score = request.form.get(score_key)
            if not score:
                flash(f"Missing score for Hole {hole[0]}", "danger")
                return redirect(url_for('enter_score', course_id=course_id, holes=holes))
            scores.append((hole[0], int(score)))  # (HoleID, Score)

        total_score = sum(score[1] for score in scores)

        # Insert scores into the database and update GamesPlayed
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Insert each score into Player_has_Score
            for hole_id, score in scores:
                cursor.execute(
                    "INSERT INTO Player_has_Score (PlayerID, CourseID, HoleID, Score, ScoreDate) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (player_id, course_id, hole_id, score, play_date)
                )

            # Update the GamesPlayed count for the player
            cursor.execute(
                "UPDATE Player SET GamesPlayed = GamesPlayed + 1 WHERE PlayerID = %s",
                (player_id,)
            )
            conn.commit()

            flash(f'Scores for {holes}-Hole Course on {play_date} Entered. Total Score: {total_score}', 'success')
            return redirect(url_for('home'))
        except mysql.connector.Error as err:
            conn.rollback()  # Rollback if there is an error
            flash(f"Error: {err}", 'danger')
        finally:
            cursor.close()
            conn.close()

    return render_template('enter_score.html', course_id=course_id, holes=holes, holes_data=holes_data, form=form)


#view scores
@app.route('/view_scores', methods=['GET'])
def view_scores():
    form = EmptyForm()
    # Ensure the user is logged in
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in to view your scores.", "danger")
        return redirect(url_for('login'))

    # Get PlayerID linked to the logged-in UserID
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT PlayerID FROM Player WHERE UserID = %s", (user_id,))
    player_data = cursor.fetchone()
    if not player_data:
        flash("Player not found for the logged-in user.", "danger")
        return redirect(url_for('home'))
    player_id = player_data[0]

    # Retrieve course and date filters
    course_id = request.args.get('course_id')
    play_date = request.args.get('play_date')

    # Fetch all courses for the dropdown
    cursor.execute("SELECT CourseID, Name FROM Course")
    courses = cursor.fetchall()

    # Fetch unique dates for the dropdown
    cursor.execute("SELECT DISTINCT ScoreDate FROM Player_has_Score WHERE PlayerID = %s", (player_id,))
    unique_dates = [row[0].strftime('%Y-%m-%d') for row in cursor.fetchall()]

    scores = []
    selected_course = None
    total_score = 0

    # Fetch scores if course and date are selected
    if course_id and play_date:
        cursor.execute("""
            SELECT h.HoleID, h.Par, ps.Score, ps.ScoreID
            FROM Player_has_Score ps
            JOIN Hole h ON ps.HoleID = h.HoleID
            WHERE ps.PlayerID = %s AND ps.CourseID = %s AND ps.ScoreDate = %s
            ORDER BY h.HoleID
        """, (player_id, course_id, play_date))
        scores = cursor.fetchall()

        # Fetch the selected course name
        cursor.execute("SELECT Name FROM Course WHERE CourseID = %s", (course_id,))
        course_result = cursor.fetchone()
        selected_course = course_result[0] if course_result else None

        # Calculate total score
        total_score = sum([score[2] for score in scores])

    cursor.close()
    conn.close()

    return render_template(
        'view_scores.html',
        courses=courses,
        scores=scores,
        selected_course=selected_course,
        selected_course_id=course_id,
        selected_date=play_date,
        unique_dates=unique_dates,
        total_score=total_score,
        form=form
    )
    
# edit scores 
@app.route('/edit_score', methods=['GET'])
def edit_score():
    form = EmptyForm()
    score_id = request.args.get('score_id')
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Fetch the existing score to be edited
        cursor.execute("""
            SELECT Score, HoleID, CourseID, ScoreDate
            FROM Player_has_Score
            WHERE ScoreID = %s
        """, (score_id,))
        score_entry = cursor.fetchone()

        if not score_entry:
            flash("Score not found.", 'danger')
            return redirect(url_for('view_scores'))

        # Pass the score data to the edit template
        return render_template('edit_score.html', score_entry=score_entry, score_id=score_id, form=form)

    except mysql.connector.Error as err:
        flash(f"Error: {err}", 'danger')
        return redirect(url_for('view_scores'))
    finally:
        cursor.close()
        conn.close()

#save scores
@app.route('/save_score', methods=['POST'])
def save_score():
    if request.is_json:
        data = request.get_json()
        score_id = data.get('score_id')
        new_score = data.get('new_score')

        if not score_id or not new_score:
            return 'Invalid data', 400

        # Update the score in the database
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE Player_has_Score 
                SET Score = %s 
                WHERE ScoreID = %s
            """, (new_score, score_id))
            conn.commit()
            return 'Score updated successfully', 200
        except mysql.connector.Error as err:
            print(f"Error updating score: {err}")
            return 'Database error', 500
        finally:
            cursor.close()
            conn.close()
    else:
        return 'Unsupported Media Type', 415

# Route for 9-hole score entry
@app.route('/enter_9_hole_score', methods=['GET', 'POST'])
def enter_9_hole_score():
    if request.method == 'POST':
        course_id = request.form['course_id']
        scores = [int(request.form[f'score_{i}']) for i in range(1, 10)]
        total_score = sum(scores)

        # Insert the score into the database (assuming the user is logged in)
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            for i, score in enumerate(scores, start=1):
                cursor.execute("INSERT INTO Player_has_Score (PlayerID, CourseID, HoleID, Score, ScoreDate) "
                               "VALUES (%s, %s, %s, %s, %s)", 
                               (session['user_id'], course_id, i, score, '2024-11-01'))  # Example date
            conn.commit()
            flash(f'9-Hole Score Entered. Total Score: {total_score}', 'success')
        except mysql.connector.Error as err:
            flash(f"Error: {err}", 'danger')
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for('home'))

    # Get course and hole data
    course_id = request.args.get('course_id')
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT HoleID, Par FROM Hole WHERE CourseID = %s", (course_id,))
    holes = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('enter_9_hole_score.html', holes=holes, course_id=course_id)  # Pass holes to template




#delete score
@app.route('/delete_score', methods=['POST'])
def delete_score():
    data = request.get_json()
    score_id = data.get('score_id')

    if not score_id:
        return jsonify({'error': 'Invalid score ID'}), 400

    # Connect to the database and delete the score
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Player_has_Score WHERE ScoreID = %s", (score_id,))
        conn.commit()
        return jsonify({'message': 'Score deleted successfully'}), 200
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()
  

#Profile:
# Profile Route to handle course and hole selection
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    form = EmptyForm()
    if 'user_id' not in session:
        flash('You need to be logged in to view your profile.', 'danger')
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Fetch user details from the database
        cursor.execute('SELECT * FROM User WHERE UserID = %s', (user_id,))
        user = cursor.fetchone()

        # Fetch available courses from the Course table
        cursor.execute('SELECT * FROM Course')
        courses = cursor.fetchall()

        print(f"User Data: {user}")  # Add print statement for user
        print(f"Courses Data: {courses}")  # Add print statement for courses

        if request.method == 'POST':
            course_id = request.form['course_id']
            holes = 9
            return redirect(url_for('enter_score', course_id=course_id, holes=holes))

    except mysql.connector.Error as err:
        flash(f"Error fetching user or courses: {err}", 'danger')
        user = None
        courses = []

    finally:
        cursor.close()
        conn.close()

    if user:
        return render_template('profile.html', user=user, courses=courses, form=form)
    else:
        flash('User not found', 'danger')
        return redirect(url_for('home'))

# Edit Profile Route
@app.route('/edit_profile', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def edit_profile():
    form = EmptyForm()
    if 'user_id' in session:
        user_id = session['user_id']
        
        if request.method == 'POST':
            # Get data from the form
            username = request.form['username']
        

            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("UPDATE User SET Username = %s WHERE UserID = %s", (username, user_id))
                conn.commit()
                flash('Profile updated successfully!', 'success')
                return redirect(url_for('profile'))
            except mysql.connector.Error as err:
                flash(f"Error: {err}", 'danger')
            finally:
                cursor.close()
                conn.close()
        
        # If GET, fetch user data
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM User WHERE UserID = %s', (user_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user:
            return render_template('edit_profile.html', user=user, form=form)
        else:
            flash('User not found', 'danger')
            return redirect(url_for('home'))
    else:
        flash('You need to be logged in to edit your profile.', 'danger')
        return redirect(url_for('login'))


# Logout Route
@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.pop('user_id', None)  # Remove user ID from session
    flash('You have been logged out.', 'info')  # Set flash message
    return redirect(url_for('home'))  # Redirect to home page


# Leaderboard Route
@app.route('/leaderboard', methods=['GET'])
def leaderboard():
    form = EmptyForm()
    selected_course_id = request.args.get('course_id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch all courses for the dropdown
    cursor.execute("SELECT CourseID, Name FROM Course")
    courses = cursor.fetchall()
    
    # If a specific course is selected, filter the leaderboard by that course
    if selected_course_id:
        query = """
            SELECT u.Username, p.Name, SUM(ps.Score) AS TotalScore, COUNT(ps.HoleID) AS HolesPlayed
            FROM Player_has_Score ps
            JOIN Player p ON ps.PlayerID = p.PlayerID
            JOIN User u ON p.UserID = u.UserID
            WHERE ps.CourseID = %s
            GROUP BY u.Username, p.Name
            ORDER BY TotalScore ASC
        """
        cursor.execute(query, (selected_course_id,))
    else:
        # Show leaderboard for all courses
        query = """
            SELECT u.Username, p.Name, SUM(ps.Score) AS TotalScore, COUNT(ps.HoleID) AS HolesPlayed
            FROM Player_has_Score ps
            JOIN Player p ON ps.PlayerID = p.PlayerID
            JOIN User u ON p.UserID = u.UserID
            GROUP BY u.Username, p.Name
            ORDER BY TotalScore ASC
        """
        cursor.execute(query)
    
    leaderboard_data = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # Assign ranks based on the sorted scores
    ranked_leaderboard = []
    previous_score = None
    rank = 0
    for index, entry in enumerate(leaderboard_data):
        username, player_name, total_score, holes_played = entry
        if total_score != previous_score:
            rank = index + 1
        ranked_leaderboard.append((rank, username, player_name, total_score, holes_played))
        previous_score = total_score
    
    return render_template(
        'leaderboard.html',
        leaderboard=ranked_leaderboard,
        courses=courses,
        selected_course_id=selected_course_id,
        form=form
    )

#performance analysis
@app.route('/performance', methods=['GET'])
def performance():
    form = EmptyForm()
    player_id = session.get('user_id')
    if not player_id:
        flash("You need to be logged in to view performance analysis", "danger")
        return redirect(url_for('home'))

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    avg_scores, weak_holes, drills = analyze_player_performance(player_id, start_date, end_date)

    return render_template(
        'performance.html',
        avg_scores=avg_scores,
        weak_holes=weak_holes,
        drills=drills,
        start_date=start_date,
        end_date=end_date,
        form=form
    )

#gen predicitons
@app.route('/generate_predictions', methods=['GET'])
def generate_predictions_route():
    # Retrieve player ID from session and course ID from query parameters
    player_id = session.get('user_id')
    course_id = request.args.get('course_id')

    # Debugging prints
    print(f"Player ID from session: {player_id}")
    print(f"Course ID from query parameter: {course_id}")

    # Validate inputs
    if not player_id:
        flash("Player ID is missing! Please log in again.", "danger")
        return redirect(url_for('home'))
    if not course_id:
        flash("Course ID is missing! Please select a course.", "danger")
        return redirect(url_for('home'))

    try:
        # Ensure course_id is an integer
        course_id = int(course_id)

        # Use the machine learning model to make predictions
        predictions = make_predictions(model, player_id, course_id)

        # Check if predictions are empty
        if predictions.empty:
            flash("Not enough data to generate predictions.", "info")
            return redirect(url_for('home'))

        course_name = predictions['CourseID'].iloc[0]  # Assuming CourseID maps to a name
        return render_template('predictions.html', course_name=course_name, predictions=predictions)
    except Exception as e:
        print(f"Unexpected error: {e}")
        flash("An error occurred while generating predictions.", "danger")
        return redirect(url_for('home'))


# COURSES  MANAGEMENT   


#add courses 
@app.route('/add_course', methods=['GET', 'POST'])
def add_course():
    form = EmptyForm()
    if request.method == 'POST':
        # Print the form data to debug
        print(request.form)

        course_name = request.form.get('course_name')
        num_holes = request.form.get('num_holes')
        location = request.form.get('location')
        rating = request.form.get('rating')

        # Check if all fields are retrieved correctly
        if not course_name or not num_holes or not location or not rating:
            flash("Please fill in all the fields.", "danger")
            return render_template('add_course.html', form=form)

        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO Course (Name, TotalHoles, Location, Rating) 
            VALUES (%s, %s, %s, %s)
        """, (course_name, num_holes, location, rating))

        conn.commit()
        cursor.close()
        conn.close()

        flash("Course added successfully!", "success")
        return redirect(url_for('view_courses'))

    return render_template('add_course.html', form=form)

#edit course
@app.route('/edit_course/<int:course_id>', methods=['GET', 'POST'])
def edit_course(course_id):
    # Check if user is admin
    if 'role' not in session or session['role'] != 'admin':
        flash("You must be an admin to edit courses.", "danger")
        return redirect(url_for('home'))

    form = EmptyForm()
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch existing course data
        cursor.execute("SELECT * FROM Course WHERE CourseID = %s", (course_id,))
        course = cursor.fetchone()
        
        if not course:
            flash("Course not found.", "danger")
            return redirect(url_for('view_courses'))

        if request.method == 'POST':
            if form.validate_on_submit():
                # Validate and sanitize inputs
                course_name = request.form.get('course_name', '').strip()
                num_holes = request.form.get('num_holes', '')
                location = request.form.get('location', '').strip()
                rating = request.form.get('rating', '')

                # Input validation
                if not all([course_name, num_holes, location, rating]):
                    flash("All fields are required.", "danger")
                    return render_template('edit_course.html', course=course, form=form)

                try:
                    num_holes = int(num_holes)
                    rating = float(rating)
                    if num_holes <= 0 or rating < 0:
                        raise ValueError
                except ValueError:
                    flash("Invalid number format for holes or rating.", "danger")
                    return render_template('edit_course.html', course=course, form=form)

                # Update the course
                cursor.execute("""
                    UPDATE Course 
                    SET Name = %s, TotalHoles = %s, Location = %s, Rating = %s 
                    WHERE CourseID = %s
                """, (course_name, num_holes, location, rating, course_id))
                
                conn.commit()
                flash("Course updated successfully!", "success")
                return redirect(url_for('view_courses'))

        return render_template('edit_course.html', course=course, form=form)

    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "danger")
        return redirect(url_for('view_courses'))
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

#delete course
@app.route('/delete_course/<int:course_id>', methods=['POST'])
def delete_course(course_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM Course WHERE CourseID = %s", (course_id,))
    conn.commit()
    
    cursor.close()
    conn.close()

    flash("Course deleted successfully!", "danger")
    return redirect(url_for('view_courses'))

#view course
@app.route('/view_courses')
def view_courses():
    if 'role' in session and session['role'] == 'admin':
        form = EmptyForm()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Course")
        courses = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('view_courses.html', courses=courses, form=form)

    flash('You must be an admin to view courses.', 'danger')
    return redirect(url_for('home'))

#view players
@app.route('/view_players', methods=['GET'])
def view_players():
    if 'user_id' in session and session.get('role') == 'admin':
        form = EmptyForm()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.PlayerID, u.Username, p.Name, p.Email 
            FROM Player p 
            JOIN User u ON p.UserID = u.UserID
            ORDER BY p.PlayerID ASC
        """)
        players = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('view_players.html', players=players, form=form)
    else:
        flash("You must be an admin to view this page.", "danger")
        return redirect(url_for('home'))

#edit player
@app.route('/edit_player/<int:player_id>', methods=['GET', 'POST'])
def edit_player(player_id):
    form = EmptyForm()
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Fetch player details based on PlayerID
        cursor.execute("""
            SELECT p.PlayerID, p.Name, p.Email, u.Username 
            FROM Player p 
            JOIN User u ON p.UserID = u.UserID 
            WHERE p.PlayerID = %s
        """, (player_id,))
        player = cursor.fetchone()

        if not player:
            flash(f"Player with ID {player_id} not found.", "danger")
            return redirect(url_for('view_players'))

        if request.method == 'POST':
            # Capture form data
            name = request.form['name']
            email = request.form['email']

            # Update the player in the database
            cursor.execute("""
                UPDATE Player 
                SET Name = %s, Email = %s 
                WHERE PlayerID = %s
            """, (name, email, player_id))
            conn.commit()

            flash("Player updated successfully!", "success")
            return redirect(url_for('view_players'))

    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "danger")
    finally:
        cursor.close()
        conn.close()

    return render_template('edit_player.html', player=player, form=form)
    
#delete player
@app.route('/delete_player/<int:player_id>', methods=['POST'])
def delete_player(player_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Delete the player record from the Player table
    cursor.execute("DELETE FROM Player WHERE PlayerID = %s", (player_id,))
    
    conn.commit()

    cursor.close()
    conn.close()

    flash('Player deleted successfully!', 'success')
    return redirect(url_for('view_players'))  # Redirect to the player list page after deletion

#manage staff
@app.route('/manage_staff')
def manage_staff():
    if 'role' in session and session['role'] == 'admin':
        form = EmptyForm()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Staff")
        staff_members = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('manage_staff.html', staff_members=staff_members, form=form)
    else:
        flash('You must be an admin to access this page.', 'danger')
        return redirect(url_for('home'))

# ADD STAFF
@app.route('/add_staff', methods=['GET', 'POST'])
def add_staff():
    form = EmptyForm()
    if request.method == 'POST':
        name = request.form['name']
        role = request.form['role']
        schedule = request.form.get('schedule', '')

        if not name or not role:
            flash("Please fill in all required fields.", "danger")
            return render_template('add_staff.html')

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO Staff (Name, Role, Schedule) 
            VALUES (%s, %s, %s)
        """, (name, role, schedule))

        conn.commit()
        cursor.close()
        conn.close()

        flash("Staff member added successfully!", "success")
        return redirect(url_for('manage_staff'))

#EDIT STAFF
@app.route('/edit_staff/<int:staff_id>', methods=['GET', 'POST'])
def edit_staff(staff_id):
    form = EmptyForm()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM Staff WHERE StaffID = %s", (staff_id,))
    staff = cursor.fetchone()

    if request.method == 'POST':
        name = request.form['name']
        role = request.form['role']
        schedule = request.form.get('schedule', '')

        cursor.execute("""
            UPDATE Staff 
            SET Name = %s, Role = %s, Schedule = %s 
            WHERE StaffID = %s
        """, (name, role, schedule, staff_id))

        conn.commit()
        cursor.close()
        conn.close()

        flash("Staff member updated successfully!", "success")
        return redirect(url_for('manage_staff'))

#DELETE STAFF
@app.route('/delete_staff/<int:staff_id>', methods=['POST'])
def delete_staff(staff_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM Staff WHERE StaffID = %s", (staff_id,))
    conn.commit()
    
    cursor.close()
    conn.close()

    flash("Staff member deleted successfully!", "danger")
    return redirect(url_for('manage_staff'))



# manage maintenance
@app.route('/manage_maintenance', methods=['GET', 'POST'])
def manage_maintenance():
    if 'user_id' in session and session.get('role') == 'admin':
        form = EmptyForm()
        conn = get_db_connection()
        cursor = conn.cursor()

        if request.method == 'POST':
            maintenance_description = request.form['description']
            maintenance_date = request.form['maintenance_date']
            course_id = request.form['course_id']  # Get the course_id from the form

            # Add new maintenance task
            cursor.execute("""
                INSERT INTO Maintenance (Description, MaintenanceDate, CourseID)
                VALUES (%s, %s, %s)
            """, (maintenance_description, maintenance_date, course_id))
            conn.commit()

        # Fetch all maintenance tasks with course names
        cursor.execute("""
            SELECT m.MaintenanceID, m.Description, m.MaintenanceDate, c.Name 
            FROM Maintenance m
            JOIN Course c ON m.CourseID = c.CourseID
            ORDER BY m.MaintenanceDate
        """)
        maintenance_tasks = cursor.fetchall()

        # Fetch all courses for the dropdown
        cursor.execute("SELECT CourseID, Name FROM Course")
        courses = cursor.fetchall()

        cursor.close()
        conn.close()

        return render_template('manage_maintenance.html', 
                             maintenance_tasks=maintenance_tasks, 
                             courses=courses, 
                             form=form)
    else:
        return redirect(url_for('home'))

# edit maintenance
@app.route('/edit_maintenance/<int:task_id>', methods=['GET', 'POST'])
def edit_maintenance(task_id):
    form = EmptyForm()
    if 'user_id' in session and session.get('role') == 'admin':
        conn = get_db_connection()
        cursor = conn.cursor()

        if request.method == 'POST':
            description = request.form['description']
            maintenance_date = request.form['maintenance_date']
            
            # Update the maintenance task in the database
            cursor.execute("""
                UPDATE Maintenance
                SET Description = %s, Date = %s  # Changed to Date
                WHERE MaintenanceID = %s
            """, (description, maintenance_date, task_id))
            conn.commit()
            
            flash('Maintenance task updated successfully!', 'success')
            cursor.close()
            conn.close()
            return redirect(url_for('manage_maintenance'))
        
        # Fetch the maintenance task to pre-fill the form
        cursor.execute("""
            SELECT Description, Date  # Changed to Date
            FROM Maintenance
            WHERE MaintenanceID = %s
        """, (task_id,))
        task = cursor.fetchone()

        cursor.close()
        conn.close()

        return render_template('edit_maintenance.html', task=task, form=form)


# delete maintenance
@app.route('/delete_maintenance/<int:task_id>', methods=['POST'])
def delete_maintenance(task_id):
    if 'user_id' in session and session.get('role') == 'admin':
        conn = get_db_connection()
        cursor = conn.cursor()

        # Delete the maintenance task from the database
        cursor.execute("""
            DELETE FROM Maintenance
            WHERE MaintenanceID = %s
        """, (task_id,))
        conn.commit()

        flash('Maintenance task deleted successfully!', 'success')
        
        cursor.close()
        conn.close()
        
        return redirect(url_for('manage_maintenance'))
    else:
        return redirect(url_for('home'))


# booking tee time
@app.route('/book_tee_time', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def book_tee_time():
    form = EmptyForm()
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            # Retrieve form data
            user_id = session.get('user_id')  # Use session for user identification
            course_name = request.form['course_name']
            booking_date = request.form['booking_date']
            tee_time = request.form['tee_time']
            number_of_players = request.form['number_of_players']

            # Fetch CourseID based on Course Name
            cursor.execute("SELECT CourseID FROM Course WHERE Name = %s", (course_name,))
            course_id = cursor.fetchone()
            if not course_id:
                flash('Invalid course selected!', 'danger')
                return redirect(url_for('book_tee_time'))

            # Insert booking
            query = """
            INSERT INTO TeeTimeBookings (UserID, CourseID, BookingDate, TeeTime, NumberOfPlayers)
            VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(query, (user_id, course_id['CourseID'], booking_date, tee_time, number_of_players))
            conn.commit()

            flash('Tee time booked successfully!', 'success')
            return redirect(url_for('book_tee_time'))

        # Fetch courses for dropdown menu
        cursor.execute("SELECT CourseID, Name FROM Course")
        courses = cursor.fetchall()

    except mysql.connector.Error as err:
        flash(f'Database error: {err}', 'danger')
        courses = []

    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn.is_connected():
            conn.close()

    # Render the page with course data
    return render_template('book_tee_time.html', courses=courses, form=form)


#view booking tee time
@app.route('/view_tee_time_bookings', methods=['GET'])
def view_tee_time_bookings():
    form = EmptyForm()
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Check user role from session
        if session.get('role') == 'admin':
            # Admin: Fetch all bookings
            query = """
            SELECT t.BookingID, u.Username, c.Name AS CourseName, t.BookingDate, t.TeeTime, t.NumberOfPlayers
            FROM TeeTimeBookings t
            JOIN User u ON t.UserID = u.UserID
            JOIN Course c ON t.CourseID = c.CourseID
            ORDER BY t.BookingDate, t.TeeTime
            """
            cursor.execute(query)
        else:
            # Regular user: Fetch only their bookings
            user_id = session.get('user_id')
            query = """
            SELECT t.BookingID, c.Name AS CourseName, t.BookingDate, t.TeeTime, t.NumberOfPlayers
            FROM TeeTimeBookings t
            JOIN Course c ON t.CourseID = c.CourseID
            WHERE t.UserID = %s
            ORDER BY t.BookingDate, t.TeeTime
            """
            cursor.execute(query, (user_id,))

        bookings = cursor.fetchall()

    except mysql.connector.Error as err:
        flash(f'Database error: {err}', 'danger')
        bookings = []

    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn.is_connected():
            conn.close()

    return render_template('view_tee_time_bookings.html', bookings=bookings, form=form)

#edit booking
@app.route('/edit_booking/<int:booking_id>', methods=['GET'])
def edit_booking(booking_id):
    form = EmptyForm()
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Fetch the booking details by BookingID
        query = """
        SELECT t.BookingID, t.BookingDate, t.TeeTime, t.NumberOfPlayers, c.Name AS CourseName
        FROM TeeTimeBookings t
        JOIN Course c ON t.CourseID = c.CourseID
        WHERE t.BookingID = %s
        """
        cursor.execute(query, (booking_id,))
        booking = cursor.fetchone()

        if not booking:
            flash('Booking not found!', 'danger')
            return redirect(url_for('view_tee_time_bookings'))

    except mysql.connector.Error as err:
        flash(f'Database error: {err}', 'danger')
        return redirect(url_for('view_tee_time_bookings'))

    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn.is_connected():
            conn.close()

    return render_template('edit_booking.html', booking=booking, form=form)

#update booking
@app.route('/update_booking/<int:booking_id>', methods=['POST'])
def update_booking(booking_id):
    form = EmptyForm()
    if form.validate_on_submit():
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Get updated form data
            new_booking_date = request.form['booking_date']
            new_tee_time = request.form['tee_time']
            new_number_of_players = request.form['number_of_players']

            # Update the booking
            query = """
            UPDATE TeeTimeBookings
            SET BookingDate = %s, TeeTime = %s, NumberOfPlayers = %s
            WHERE BookingID = %s
            """
            cursor.execute(query, (new_booking_date, new_tee_time, new_number_of_players, booking_id))
            conn.commit()

            flash('Booking updated successfully!', 'success')

        except mysql.connector.Error as err:
            flash(f'Database error: {err}', 'danger')

        finally:
            if 'cursor' in locals() and cursor:
                cursor.close()
            if 'conn' in locals() and conn.is_connected():
                conn.close()

        return redirect(url_for('view_tee_time_bookings'))

# Add error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    logging.error(f"Server error: {e}")
    return render_template('500.html'), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))  # Changed from 5000 to 5001
    app.run(host='0.0.0.0', port=port)
    
