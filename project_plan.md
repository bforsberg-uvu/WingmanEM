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

### Application Flow & UI

- UI and app functionality should be performant
- Navigation and app flow should be logical and intuitive

### Error Reporting

- Errors should be handled appropriately and reported when necessary

### Testing

- Should have AI Automated test which can be run to ensure functional continuity and reliability as the application evolves

## Data Model

### Table: Direct_Reports

| Attribute | Data Type | Rationale |
|-----------|-----------|-----------|
| id | INTEGER | Primary Key. Use AUTO_INCREMENT (MySQL) or PRIMARY KEY (SQLite). |
| first_name | VARCHAR(50) | Standard length for names. |
| last_name | VARCHAR(50) | Stored separately to enable easy sorting and "Wingman" personalization. |
| street_address_1 | VARCHAR(100) | Primary address line for care packages or local information. |
| street_address_2 | VARCHAR(100) | Optional field for apartment or suite numbers; allow NULL. |
| city | VARCHAR(50) | (Added for completeness) Required for proper address structure. |
| state | CHAR(2) or VARCHAR(50) | Use CHAR(2) if you strictly use ISO codes (e.g., "UT"); VARCHAR for global flexibility. |
| zipcode | VARCHAR(10) | Use VARCHAR to handle leading zeros (e.g., 02108) and international postal codes. |
| country | VARCHAR(50) | Helpful for EMs managing distributed/global teams. |
| birthday | DATE | Store as YYYY-MM-DD. Used for your "Important Events" reminders. |
| hire_date | DATE | Critical for calculating total company tenure and work anniversaries. |
| current_role | VARCHAR(100) | Descriptive title (e.g., "Senior Software Engineer"). |
| role_start_date | DATE | Used to calculate "Tenure in Role" to identify when a report might be due for a promotion or new challenge. |
| partner_name | VARCHAR(50) | Valuable "soft" data for building rapport during 1:1s. |

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

### 7