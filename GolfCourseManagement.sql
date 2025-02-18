-- * main database
USE mydb;

DESCRIBE TeeTimes;

INSERT INTO TeeTimes (CourseID, PlayerID, TeeTime)
VALUES 
    (1, 1, '2024-12-01 08:00:00'),
    (1, 3, '2024-12-01 09:00:00'),
    (2, 3, '2024-12-01 10:00:00'),
    (2, 1, '2024-12-01 11:00:00'),
    (1, 1, '2024-12-02 08:00:00'),
    (1, 3, '2024-12-02 09:00:00');

Select * From Player;






-- * CREATE TABLES

CREATE TABLE User (
    UserID INT PRIMARY KEY,
    Username VARCHAR(50) UNIQUE NOT NULL,
    Password VARCHAR(255) NOT NULL
);

-- * Course Table
CREATE TABLE Course (
    CourseID INT PRIMARY KEY,
    Name VARCHAR(100) NOT NULL,
    Location VARCHAR(100),
    TotalHoles INT NOT NULL,
    Rating DECIMAL(5, 1)
);

-- * Hole Table
CREATE TABLE Hole (
    HoleID INT PRIMARY KEY,
    CourseID BIGINT UNSIGNED NOT NULL,
    Par INT NOT NULL,
    Distance INT NOT NULL,
    FOREIGN KEY (CourseID) REFERENCES Course(CourseID) ON DELETE CASCADE
);


-- * Player Table
CREATE TABLE Player (
    PlayerID SERIAL PRIMARY KEY,
    Name VARCHAR(100) NOT NULL,
    Email VARCHAR(100),
    PhoneNumber VARCHAR(15),
    GamesPlayed INT DEFAULT 0
);
ALTER TABLE Player 
ADD UserID BIGINT UNSIGNED,
ADD FOREIGN KEY (UserID) REFERENCES User(UserID) ON DELETE CASCADE;


-- * Staff Table
CREATE TABLE Staff (
    StaffID SERIAL PRIMARY KEY,
    Name VARCHAR(100) NOT NULL,
    Role VARCHAR(50) NOT NULL,
    Schedule VARCHAR(50)
);
-- * Maintenance Table
CREATE TABLE Maintenance (
    MaintenanceID SERIAL PRIMARY KEY,
    CourseID BIGINT UNSIGNED NOT NULL,
    Description TEXT,
    Date DATE NOT NULL,
    FOREIGN KEY (CourseID) REFERENCES Course(CourseID) ON DELETE CASCADE
);

-- * WorksOn Table (Associative Entity connecting Staff and Course)
CREATE TABLE IF NOT EXISTS WorksOn (
  AssignmentID INT NOT NULL AUTO_INCREMENT,
  StaffID BIGINT UNSIGNED NOT NULL,               -- Matches Staff.StaffID
  CourseID BIGINT UNSIGNED NOT NULL,              -- Matches Course.CourseID
  AssignmentDate DATE NOT NULL,
  PRIMARY KEY (AssignmentID),
  INDEX fk_WorksOn_Staff_idx (StaffID ASC),
  INDEX fk_WorksOn_Course_idx (CourseID ASC),
  CONSTRAINT fk_WorksOn_Staff
    FOREIGN KEY (StaffID)
    REFERENCES Staff(StaffID)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT fk_WorksOn_Course
    FOREIGN KEY (CourseID)
    REFERENCES Course(CourseID)
    ON DELETE CASCADE
    ON UPDATE CASCADE
);

-- * Player_has_Score
CREATE TABLE IF NOT EXISTS Player_has_Score (
  ScoreID INT NOT NULL AUTO_INCREMENT,
  CourseID BIGINT UNSIGNED NOT NULL,        -- Matches Course.CourseID
  HoleID INT NOT NULL,                      -- Matches Hole.HoleID
  PlayerID BIGINT UNSIGNED NOT NULL,        -- Matches Player.PlayerID
  Score INT NOT NULL,
  TotalScore INT NOT NULL,
  ScoreDate DATE NOT NULL,
  PRIMARY KEY (ScoreID),
  INDEX fk_Player_has_Score_Player_idx (PlayerID ASC),
  INDEX fk_Player_has_Score_Course_idx (CourseID ASC),
  INDEX fk_Player_has_Score_Hole_idx (HoleID ASC),
  CONSTRAINT fk_Player_has_Score_Course
    FOREIGN KEY (CourseID)
    REFERENCES Course(CourseID)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT fk_Player_has_Score_Hole
    FOREIGN KEY (HoleID)
    REFERENCES Hole(HoleID)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT fk_Player_has_Score_Player
    FOREIGN KEY (PlayerID)
    REFERENCES Player(PlayerID)
    ON DELETE CASCADE
    ON UPDATE CASCADE
    
);
ALTER TABLE Player_has_Score ADD COLUMN Editing BOOLEAN DEFAULT FALSE;
-- * Player_has_Course
CREATE TABLE IF NOT EXISTS Player_has_Course (
  PlayerCourseID INT NOT NULL AUTO_INCREMENT,
  CourseID BIGINT UNSIGNED NOT NULL,        -- Matches Course.CourseID
  HoleID INT NOT NULL,                      -- Matches Hole.HoleID
  PlayerID BIGINT UNSIGNED NOT NULL,        -- Matches Player.PlayerID
  PlayDate DATE NOT NULL,
  PRIMARY KEY (PlayerCourseID),
  INDEX fk_Player_has_Course_Player_idx (PlayerID ASC),
  INDEX fk_Player_has_Course_Course_idx (CourseID ASC),
  INDEX fk_Player_has_Course_Hole_idx (HoleID ASC),
  CONSTRAINT fk_Player_has_Course_Course
    FOREIGN KEY (CourseID)
    REFERENCES Course(CourseID)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT fk_Player_has_Course_Hole
    FOREIGN KEY (HoleID)
    REFERENCES Hole(HoleID)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT fk_Player_has_Course_Player
    FOREIGN KEY (PlayerID)
    REFERENCES Player(PlayerID)
    ON DELETE CASCADE
    ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS PlayerTotalScore (
    PlayerID INT NOT NULL,
    CourseID INT NOT NULL,
    TotalScore INT DEFAULT 0,
    PRIMARY KEY (PlayerID, CourseID)
);
DELIMITER //

CREATE TRIGGER update_total_score_after_insert_update
AFTER INSERT ON Player_has_Score
FOR EACH ROW
BEGIN
    INSERT INTO PlayerTotalScore (PlayerID, CourseID, TotalScore)
    VALUES (NEW.PlayerID, NEW.CourseID, NEW.Score)
    ON DUPLICATE KEY UPDATE TotalScore = TotalScore + NEW.Score;
END //

DELIMITER ;
DELIMITER //

CREATE TRIGGER update_total_score_after_delete
AFTER DELETE ON Player_has_Score
FOR EACH ROW
BEGIN
    UPDATE PlayerTotalScore
    SET TotalScore = TotalScore - OLD.Score
    WHERE PlayerID = OLD.PlayerID AND CourseID = OLD.CourseID;
END //

DELIMITER ;

CREATE TABLE UserActivityLog (
    ActivityID INT AUTO_INCREMENT PRIMARY KEY,
    UserID BIGINT UNSIGNED,
    Activity VARCHAR(255),
    ActivityDate DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (UserID) REFERENCES User(UserID) ON DELETE CASCADE ON UPDATE CASCADE
);
DESCRIBE User;

CREATE TABLE IF NOT EXISTS teetime (
    TeeTimeID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    CourseID BIGINT UNSIGNED NOT NULL,
    PlayerID BIGINT UNSIGNED NOT NULL,
    TeeTime DATETIME NOT NULL,
    PRIMARY KEY (TeeTimeID),
    FOREIGN KEY (CourseID) REFERENCES Course(CourseID),
    FOREIGN KEY (PlayerID) REFERENCES Player(PlayerID)
);






-- * INSERT QUERIES

-- * add new user
INSERT INTO User (Username, Password)
VALUES ('golfplayer1', 'hashed_password_here');

-- * add new course
INSERT INTO Course (CourseID, Name, Location, TotalHoles, Rating)
VALUES (1, 'Sunny Greens', 'California', 18, 121.5);

-- * add new hole
INSERT INTO Hole (HoleID, CourseID, Par, Distance)
VALUES (1, 1, 4, 350);

-- * add new player
-- 1
INSERT INTO Player (PlayerID, Name, Email, PhoneNumber, GamesPlayed)
VALUES (1, 'John Doe', 'johndoe@example.com', '123-456-7890', 10);
	-- 1a. Insert User:
INSERT INTO User (Username, Password) VALUES ('new_user', 'hashed_password_here');
	-- 	2.	Retrieve User ID:
SELECT * FROM User WHERE Username = 'new_user';
	-- 3. Insert Player:
INSERT INTO Player (Name, Email, PhoneNumber, GamesPlayed, UserID) 
VALUES ('John Doe', 'johndoe@example.com', '123-456-7890', 0, <UserID>);
	-- 4. Check Player:
SELECT * FROM Player WHERE UserID = <UserID>;
-- Insert New Players with UserID: Update your INSERT queries for the Player table to include the UserID.
-- Example: Insert a new player associated with a user
INSERT INTO Player (Name, Email, PhoneNumber, GamesPlayed, UserID) 
VALUES ('New Player', 'newplayer@example.com', '987-654-3210', 0, @last_id);
-- Select Players by UserID: Update your SELECT queries to retrieve players based on their associated UserID.
SELECT * FROM Player WHERE UserID = @last_id;
-- Update Players: If you need to update player information, ensure you include the UserID in your WHERE clause if necessary.
UPDATE Player 
SET Email = 'updatedemail@example.com'
WHERE PlayerID = @player_id AND UserID = @last_id;
-- Delete Players: When deleting players, you can also check for UserID to ensure you’re modifying the correct record.
DELETE FROM Player 
WHERE PlayerID = @player_id AND UserID = @last_id;




-- * add new staff
INSERT INTO Staff (StaffID, Name, Role, Schedule)
VALUES (1, 'Jane Smith', 'Groundskeeper', 'Mon-Fri');

-- * add new maintenance
INSERT INTO Maintenance (MaintenanceID, CourseID, Description, Date)
VALUES (1, 1, 'Mowing and trimming', '2024-11-01');

-- * add new workson
INSERT INTO WorksOn (AssignmentID, StaffID, Name, CourseID, AssignmentDate)
VALUES (1, 1, 1, '2024-11-01');

-- * add new Player_has_course
INSERT INTO Player_has_Course (PlayerID, CourseID, HoleID, PlayDate)
VALUES (1, 1, 1, '2024-10-15');

-- * add new Player_has_Score
INSERT INTO Player_has_Score (PlayerID, CourseID, HoleID, Score, ScoreDate)
VALUES (1, 1, 1, 85, '2024-11-01');

 -- Log user activities
INSERT INTO UserActivityLog (UserID, Activity) VALUES (1, 'User logged in');
INSERT INTO UserActivityLog (UserID, Activity) VALUES (1, 'Logged out');

-- * Registration
INSERT INTO User (Username, Password) VALUES ('newUser', 'hashed_password_here');
-- Login
SELECT Password FROM User WHERE Username = 'user_input_username';

-- * SELECT queries
SELECT * FROM Course;

SELECT * FROM Hole
WHERE CourseID = 1;

SELECT * FROM Player
WHERE GamesPlayed > 5;

SELECT s.Name, s.Role, w.AssignmentDate
FROM Staff s
JOIN WorksOn w ON s.StaffID = w.StaffID
WHERE w.CourseID = 1;

SELECT Description, Date
FROM Maintenance
WHERE CourseID = 1;

SELECT p.Name, AVG(ps.Score) AS avg_score
FROM Player p
JOIN Player_has_Score ps ON p.PlayerID = ps.PlayerID
GROUP BY p.PlayerID, p.Name
ORDER BY avg_score ASC
LIMIT 5;

-- advanced function
SELECT 
    p.PlayerID, 
    u.Username, 
    p.Name AS PlayerName, 
    phs.CourseID, 
    c.Name AS CourseName, 
    phs.HoleID, 
    h.Par, 
    phs.Score, 
    phs.ScoreDate
FROM 
    Player_has_Score phs
JOIN Player p ON phs.PlayerID = p.PlayerID
JOIN User u ON p.UserID = u.UserID
JOIN Course c ON phs.CourseID = c.CourseID
JOIN Hole h ON phs.HoleID = h.HoleID
ORDER BY phs.ScoreDate DESC;



-- * UPDATE queries

UPDATE Player
SET GamesPlayed = GamesPlayed + 1
WHERE PlayerID = 1;

UPDATE Course
SET Rating = 4.7
WHERE CourseID = 1;

UPDATE Staff
SET Schedule = 'Tue-Sat'
WHERE StaffID = 1;

UPDATE User 
SET Password = 'new_hashed_password' 
WHERE Username = 'user_input_username';

-- * DELETE queries
DELETE FROM User
WHERE Username = 'golfplayer1';

DELETE FROM Course
WHERE CourseID = 1;

DELETE FROM Maintenance
WHERE MaintenanceID = 1;

DELETE FROM WorksOn
WHERE AssignmentID = 1;

DELETE FROM Player 
WHERE PlayerID = @player_id AND UserID = @last_id;


UPDATE Player_has_Score ps
JOIN (
    SELECT PlayerID, CourseID, SUM(Score) AS TotalScore
    FROM Player_has_Score
    GROUP BY PlayerID, CourseID
) AS totals ON ps.PlayerID = totals.PlayerID AND ps.CourseID = totals.CourseID
SET ps.TotalScore = totals.TotalScore;