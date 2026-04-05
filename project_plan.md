# Instructions
You are a master python coder and the following markdown gives an overview of an application I want your help creating. The project and github repository have already been created in the current directory and on Github. I want to create this program in chunks, starting with 'Chunk #1'. I will progressively add chunks to this document as we iteratively build the app. 

# WingmanEM (Engineering Manager) Application

## General Vision and Goal

WingmanEM is an intelligent co-pilot designed to offload the cognitive burden of modern Engineering Management. By automating high-frequency administrative tasks and providing AI-driven leadership insights, the app enables EMs to shift their focus from "managing tickets" to "leading people." The MVP streamlines three critical pillars: Project Lifecycle Management (automating spec-to-ticket workflows with Jira), People Operations (distilling 1:1 insights and tracking team milestones), and Continuous Leadership Development (delivering personalized daily coaching). Built with a robust SQL backend and integrated with Jira and SMS, Wingman EM ensures that critical project and people data are always actionable and never forgotten.

## Core Features (High-level user stories)

### Project Creation & Estimation

- As an Engineering Manager, I want to input a project spec so that I can receive a structured breakdown of epics and stories.
- As an Engineering Manager, I want to sync the AI-generated breakdown directly to Jira so that I don't have to manually create and format tickets.
- As an Engineering Manager, I want to ask natural language questions about my project's status so that I can get an update without digging through dashboards.

### People Management & Coaching

- As an Engineering Manager, I want a upload a audio recording of my 1:1s and have AI summarize and create action items so that neither I nor my direct report drop the ball on our commitments.
- As an Engineering Manager, I want the app to analyze 1:1 trends over several months so that I can identify recurring themes (like burnout or stagnation) that I might miss in the day-to-day.
- As an Engineering Manager, I want AI-suggested follow-up topics based on previous meetings so that our conversations remain continuous and meaningful.
- As an Engineering Manager, I want proactive reminders for "human" milestones (anniversaries, birthdays) so that I can foster a supportive team culture effortlessly.

### Manager/Management Improvement

- As an Engineering Manager, I want to receive a daily 60-second management tip or "bite-sized" story so that I can continuously improve my leadership skills without dedicated study time.

## Target Audience

While WingmanEM is purpose-built for Software Engineering Managers addressing the specific complexities of the SDLC and technical team dynamics its modular design provides a blueprint for broader leadership. The MVP leverages specialized integrations like Jira to solve the immediate pain points of technical leads. However, the core engine centered on project estimation, behavioral coaching, and proactive management is industry agnostic. Future iterations could generalize these features to empower Project Managers and People Leaders across all business functions.

## Technical Stack and Architecture

- **Database:** SQLite or MySQL
- **Backend:** Python
- **AI:** Mistral AI
- **Frontend:** HTML and CSS
- **Deployment:** Heroku

## Non-Functional Requirements

### Security

- UI should be password protected
- All traffic must be served over SSL/TLS
- Stored data should not be available outside of the app except where designated (ie. Jira, texts)

#### Per-user data isolation (web)

- The Flask app is **multi-tenant by user**: each signed-in user only loads and mutates rows tied to their account. Direct reports (and goals, 1:1s, comp flows, and management tips where the schema supports it) are scoped with an `owner_user_id` foreign key to the application user.
- **Legacy / orphan rows:** rows created before ownership existed may have `owner_user_id` NULL. When the **first** application user registers and the user table was previously empty, those orphan rows are assigned to that new user so an upgraded or single-admin install does not lose data. Subsequent registrations do **not** claim orphans; new users start with an empty dataset unless they create their own records.

### Application Flow & UI

- UI and app functionality should be performant
- Navigation and app flow should be logical and intuitive

### Error Reporting

- Errors should be handled appropriately and reported when necessary

### Testing

- Should have AI Automated test which can be run to ensure functional continuity and reliability as the application evolves

## Data Model

The live database is **SQLite** accessed through **SQLAlchemy**. Column types below match the implemented schema (`wingmanem/orm_models.py`); string and date-like fields are stored as **TEXT** (dates as ISO strings such as `YYYY-MM-DD` where used).

### Table: Users (`users`)

| Attribute | Data Type | Rationale |
|-----------|-----------|-----------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | Surrogate key for each application account. |
| first_name | TEXT NOT NULL | Display name; default empty string in DDL. |
| last_name | TEXT NOT NULL | Display name; default empty string in DDL. |
| login_id | TEXT NOT NULL UNIQUE | User-facing identifier used at login (not the numeric `id`). |

### Table: User_Passwords (`user_passwords`)

| Attribute | Data Type | Rationale |
|-----------|-----------|-----------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | Surrogate key for the password row. |
| user_id | INTEGER NOT NULL UNIQUE, FK → `users.id` ON DELETE CASCADE | One password row per user; deleting the user removes the hash. |
| password_hash | TEXT NOT NULL | Werkzeug-style password hash; never store plaintext passwords. |

### Table: Direct_Reports (`direct_reports`)

| Attribute | Data Type | Rationale |
|-----------|-----------|-----------|
| id | INTEGER PRIMARY KEY | Primary key; application assigns ids when adding reports (not database autoincrement). |
| first_name | TEXT | Required in app logic for a valid record; stored as TEXT. |
| last_name | TEXT | Same as `first_name`. |
| street_address_1 | TEXT NULL | Primary address line for care packages or local information. |
| street_address_2 | TEXT NULL | Optional suite or second line. |
| city | TEXT NULL | City for address structure. |
| state | TEXT NULL | Region or state (e.g., ISO code or full name). |
| zipcode | TEXT NULL | Preserves leading zeros and international formats. |
| country | TEXT NULL | Useful for distributed teams. |
| birthday | TEXT NULL | ISO date string when set; supports milestone reminders. |
| hire_date | TEXT NULL | Tenure and anniversary calculations. |
| current_role | TEXT NULL | Job title (e.g., "Senior Software Engineer"). |
| role_start_date | TEXT NULL | Tenure-in-role for growth conversations. |
| partner_name | TEXT NULL | Optional rapport context for 1:1s. |
| owner_user_id | INTEGER NULL, FK → `users.id` | Web app: scopes the row to the owning account; see *Per-user data isolation* under Security. |

### Table: Management_Tips (`management_tips`)

| Attribute | Data Type | Rationale |
|-----------|-----------|-----------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | Tip row identifier. |
| date | TEXT NOT NULL | Tip date label or stamp (as stored by the app). |
| text | TEXT NOT NULL | Body of the management tip or coaching snippet. |
| owner_user_id | INTEGER NULL, FK → `users.id` | When set, tip is visible only to that user in the web app. |

### Table: One_To_One_Summaries (`one_to_one_summaries`)

| Attribute | Data Type | Rationale |
|-----------|-----------|-----------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | Summary row identifier. |
| direct_report_id | INTEGER NOT NULL | Links the summary to a direct report (enforced in app routes by ownership of that report). |
| date | TEXT NOT NULL | When the 1:1 or upload was summarized. |
| response_text | TEXT NOT NULL | AI or stored summary / action text. |

### Table: Direct_Report_Goals (`direct_report_goals`)

| Attribute | Data Type | Rationale |
|-----------|-----------|-----------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | Goal row identifier. |
| direct_report_id | INTEGER NOT NULL | Foreign key to the direct report; goals are deleted when that report is removed (app/DB logic). |
| goal_title | TEXT NULL | Short title for the goal. |
| goal_description | TEXT NULL | Longer description. |
| goal_completion_date | TEXT NULL | Target completion date as stored (typically ISO). |

### Table: Direct_Report_Comp_Data (`direct_report_comp_data`)

| Attribute | Data Type | Rationale |
|-----------|-----------|-----------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | Row identifier for generated comp inputs. |
| direct_report_id | INTEGER NOT NULL | Associates comp data with a direct report. |
| first_name | TEXT NOT NULL | Snapshot for letters and display (may mirror the report). |
| last_name | TEXT NOT NULL | Same as `first_name`. |
| rating | INTEGER NOT NULL | Performance rating 1–5 driving template paragraph selection. |
| salary | INTEGER NOT NULL | Base annual salary in whole dollars before adjustment. |
| percent_change | REAL NOT NULL | Compensation change in percentage points (e.g., `5.0` means 5% of base salary). |
| dollar_change | INTEGER NOT NULL | Dollar amount of the raise (whole dollars). |
| new_salary | INTEGER NOT NULL | Salary after applying the change (whole dollars). |
| bonus | INTEGER NOT NULL | Bonus amount for the cycle (whole dollars). |


## Program Chunks

### Chunk #1:
For this chuck, create a working CLI prototype that implements the following:

Core files to create:
app.py - main application file

Core files to update:
requirements.txt

This prototype should be able to do the following: 
The app should present a gui 'main' menu to the user with a selection mechanism to select one of the app core feature areas which upon selection will take a user to one of these functional sub areas and provide them with a selection mechanism to do one of the tasks specified in the sub area.
The user should be able to navigate from the functional sub areas back to the main menu area.
The app should also provide a way for the user to exit the app.
The non functional requirements that are applicable should be met.

### Chunk #2:
To implement this chunk, refactor the dataclass DirectReport and add persistance through file saving according the the instruction below

Core files to update:
app.py
requirements.txt

The WingmanEM prototype should be able to do the following after implementing this chunk:
DirectReports should be refactored to be a dictionary object instead of a Dataclass. The keys of the dictionary should mirror the names contained in the dataclass being refactored. DirectReports should still be stored in a global variable List 'direct_reports' 
The ability to 'Delete a direct report' should be added to the Administer Direct Report Menu.
When 'Delete a direct report' is Selected the user should be prompted to enter the number of the direct report to be deleted followed by having to press enter. The program then should remove the direct report specified from the list.
The 'List direct reports' function should be able to iterate through the 'direct_reports' list.
whenever a direct report is added or deleted the global variable list 'direct_report' should be written out (mirrored) to a file. When the program starts up, this file should be read into the global variable 'direct_reports'
The file and global variable 'direct_reports' should contain the same data.
The DirectReport dictionary should be refactored to mirror the Table Direct_Reports structure specified above. All elements in DirectReports should be optional except first_name, last_name and id. All functionality should be updated for this change to DirectReport.

### Chunk #3:
To implment this chunk, add a SQLite database to manage perisistence with the following criteria:

Core files to update:
app.py
requirements.txt

Add a SQLite database to this project
Create tables for direct reports and management tips in the database and model these table after the data contained in the direct_reports.json and management_tips.json file respectively.
Populate these tables with the data contained in the direct_reports.json and management_tips.json files
Update the all the app functionality that manipulates the data in the the direct_reports.json and management_tips.json files to do the same manipulation in the database so that the files and the database stay in sync with the same data.
When listing direct reports or management tips the user the results should be shown from both the file and database seperately.
The app should function the same as they have before this change with the addition of having the data housed in the database.

### Chunk #4:
To implement this chunk we want to convert this CLI app to a Flask Web app with the following criteria:

Import flask library and configure the app.
Define a single functional route that take the user to the main menu
Convert the existing menus and functionality to work in flask.
Use professional colors in the app and user color consistently throughout the app.
Indicate the app is doing something by displaying a fun animation.
Create a web_app.py file that is the root of the app.
Run the flask server and start the app when the web_app.py script is executed

### Chunk #5:
To implement this chunk we want to add a section for employee goals with the following criteria

Create the database table direct_report_goals according the the specification contained the data model section of this file.
Create a json file to store the same data.
Add an menu item to the people coaching and management menu of the the app to admin administer direct report goals.
Clicking on this item will take the user to another menu title 'Administer Direct Report's Goals' which will have the following items:  Add Goal, View Goals, Remove Goals.
Add an flask route: /add which will display a form that allow me to select the direct report I want to add the goal for, input the goal title, the goal description and specify a completion date. 
The add form should be stored in the 'templates' folder
The form should have a button to save the information which when pressed send a POST request to another flask route /add_goal which will extract the data, structure it as a dictionary and save it to both the created json file and direct_report_goals database table.  The json file and database table should always be in sync. Once the data has been saved the user should be directed to another Flask route /goal_successfully_added.
The goal_successfully_added route should display the actual POST request that was used in the previous step as well as a user friend version of the post request on the screen. It should also display the dictionary that the data was structured as and the json file and database table contents. There should be a button to take the user back to the goal adminstration menu.
If the direct report is deleted the associated goal data should be deleted from both the json file and database.
When the user clicks on the 'View Goals' take the user to a new route /view which should present a table listing the direct reports which have goals.  The table should have a button to select the direct report.
When the user click on the button to select the direct a GET Request should be generated to a route called /view_direct_report_goals to retrieve the direct reports goals. 
The /view_direct_report_goals should display the goal in a nice tabular format.  The actual get request sent to this route should be also displayed below as well as a user friendy version for the user to view.  There should be a button to return the user to the main goal admin menu.


### Chunk #6:
To implement this chunk, create another area in the application under 'People Management & Coaching' to create direct reports compensation change statements with the following criteria 
Add Jinja2 to the project.
Create a Jinja2 template letter for a direct report for their yearly compensation adjustment. This template should allow substitution of name, percentage compensation change, dollar compensation change, bonus amount, and a rating from 5 to 1 with this breakdown:  5 - Exceptional Contribution, 4 - Exceed Expectations,  3 - Meets Expectations,  2 - Missed Expectations,  1 - Needs improvement.    Create a paragraph for each of these rating that will be displayed based on the rating substitution. 
Add a button under 'Adminster Direct Reports' title 'Generate Direct Report Ratings' which will create a direct_report_comp_data.json file from the list of current direct reports and randomly assign a rating (1 to 5) to each direct report, a salary, a percentage compensation change, a dollar compensation change which is derived by multiplying the salary by the percentage compensation change and adding it to the original salary, a random bonus amount ranging from $10000 to $30000 which is reflective of the rating recieved. Each time the button is pressed regenerate the file.
Create a route called '/items' which is reached by pressing the 'Generate Direct Report Comp Statements' that handles a get request and reads in and parses all the data from the direct_report_comp_data.json file into a dictionary and then uses a for loop in the template letter created earlier to generate compensation statement for each of the direct reports. 
The compensation statements should be presented to the user in a tabular format allow them to open each one individually. 

### Chunk #7:
To implement this chunk refactor all the database functionality in the app to use SQLAlchemy with SQLite with the following criteria.
Generate SQLAlchemy models for all existing database tables.
Refactor the app to utilize SQLAlchemy models and sql queries to perform all database operations including add, list, remove items, etc. 
Add a section to the developer menu which will show the user the various database table definitions and the associated SQLAlchemy models side by side in a easy to read format that is consistent with the rest of the app.
Add a section the developer menu that shows step by step how Direct report comp statements are generated using sql, sqlalchemy models and jinja templates. Include appropriate code examples of queries, models and templates to aid in understanding
Add another seection that show step by step how direct report ratings are generated using sql, sqlalchemy models and jinja templates. Include appropriate code examples of queries, models and templates to aid in understanding
Continue to keep json file and the database in sync.
Remove the json file comparison sections from the app just keeping the database sections. 

### Chunk #8:
To implement this chunk add edit and delete functionality for direct reports with the following criteria
Create a route /edit/<item_id> where item_id represent the id of the direct report.
Create an 'Edit' Button for each direct report record in the direct report table which routes the user to the edit route specified above.
When the user goes to the edit route a form similar to the one that is used to add a direct report is displayed populated with the coresponding direct report's data.
The user can edit this data and save the changes.
Refactor the functionality to delete a direct report so that when the delete button is pressed the user is taken to a /delete/<item_id> route where item_id represents the direct report being deleted.
A confirmation dialog should be displayed to make sure the user want to do the delete.  If the user confirms the direct report is deleted and the user is returned to the table view of direct report otherwise the user is just returned to the table view of direct reports.

### Chunk #9:
To implement this chunk add user authentication and secure the app with the following criteria
Add user authentication using Flask-Login + Werkzeug
Create a database users table which will store the application user's first and last name and user id and a password table which will store the user's hashed password.  These two tables should have a 1 to 1 foriegn key relationship with a cascading delete. 
Add a section to the developer menu that allows the developer to view the system users data with the hashed password in a table format.
Add a login page as an entry point for the app with a Create Account link that allow a user to create an account with a password and then returns the user to the login page.
The login page should require a user id and password in order to login and in the event of a successful login an authenticated flask session should be created and the user should be taken to the main page of the app.  Place a greeting to the user using the user's name in the upper right corner of the app main page.  In the event of a unsuccessful login the user should be alerted and allowed to try again. 
A logout button should be added to the main page.  When the user clicks on this button the authenticated flask session should be cleared and the user should be taken to the login screen.
All areas in the app should be secured so that the user must be authenticated to access any area in the app.

