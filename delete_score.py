@app.route('/delete_score/<int:score_id>', methods=['POST'])
def delete_score(score_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            DELETE FROM Player_has_Score 
            WHERE ScoreID = %s
        """, (score_id,))
        conn.commit()
        flash('Score deleted successfully!', 'success')
        return redirect(url_for('view_scores'))  # Redirect to view scores page
    except mysql.connector.Error as err:
        flash(f"Error: {err}", 'danger')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('view_scores'))  # Redirect if an error occurs