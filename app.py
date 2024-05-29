from flask import Flask , render_template , url_for , request , session , Response , redirect ,jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import cv2
import face_recognition
import threading
import os
import shutil

app = Flask(__name__)

app.secret_key = '120724'
app.config['UPLOAD_FOLDER'] = 'static/classes'  # Directory where class subdirectories are stored
app.config['ALLOWED_EXTENSIONS'] = {'jpeg', 'jpg'}

db_config = {
    'user': "root",
    'password': "shivam123",
    'host': 'localhost',
    'database': "sams"
}
# Global variable to control the thread
stop_event = threading.Event()

def get_db_connection():
    return mysql.connector.connect(**db_config)

@app.route("/")
def index():
    if len(session.values()) != 0:
        session.clear()
    return render_template("landing.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/signup")
def register():
    return render_template("signup.html")

@app.route("/validate" , methods=['POST'])
def validate():
    mail = request.form['mail']
    password1 = request.form['pass']
    password2 = request.form['confirm']
    name = request.form['name']
    if(password1 != password2):
        return render_template("signup.html",status="unmatch")
    if(len(password1)<4):
        return render_template("signup.html",status="short")
    else:
        try:
            mydb = get_db_connection()
            mycursor = mydb.cursor()
            password_hash = generate_password_hash(password1)
            sql = (f"INSERT INTO login_data (`email`,`password`,`name`)VALUES ('{mail}', '{password_hash}','{name}');")
            mycursor.execute(sql)
            mydb.commit()
            return render_template("login.html",status="success")
        except Exception as e:
            print(e)
            return render_template("signup.html",status="error")
        
@app.route("/loginval",methods=['POST']) 
def logsuc():
    try:
        username = request.form['mail']
        password = request.form['pass']
        con=get_db_connection()
        cursor = con.cursor(dictionary=True)
        try:
            cursor.execute(f"select * from login_data where email = '{username}';")
            result = cursor.fetchone()
        except Exception as e:
            print(e)
            return render_template("login.html",status="fail")
    except:
        print("con failed")
    
    if(result == None):
        return render_template("login.html",status="fail")
    if result['email'] == username and check_password_hash(result['password'], password):
        print("user authenticated")
        session.clear()
        session['name']= result['name']
        session['id']=result['Id']
        return render_template("home.html",username=session['name'])
    
    print("not matched")
    return render_template("login.html",status="fail")

@app.route("/home")
def home():
    if len(session.values()) == 0:
         return render_template("login.html")
    attendancelist.clear()
    con=get_db_connection()
    cursor = con.cursor(dictionary=True)
    cursor.execute(f'SELECT * FROM class_schedule where teacher_id={session['id']};')
    classes = cursor.fetchall()
    cursor.close()
    con.close()
    return render_template("home.html",username=session['name'] , classes=classes)

@app.route('/add_class', methods=['GET', 'POST'])
def add_class():
    if request.method == 'POST':
        class_name = request.form['class_name']
        start_time = request.form['start_time']
        end_time = request.form['end_time']
        day_of_week = request.form['day_of_week']
        teacher_id = session['id']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO class_schedule (class_name, start_time, end_time, day_of_week, teacher_id) VALUES (%s, %s, %s, %s, %s)',
                       (class_name, start_time, end_time, day_of_week, teacher_id))
        conn.commit()
        cursor.close()
        conn.close()

        return redirect(url_for('home'))
    return render_template('add_class.html')

@app.route('/update_completion/<int:class_id>', methods=['POST'])
def update_completion(class_id):
    completed = request.form.get('completed') == 'on'
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f'UPDATE class_schedule SET completed = {completed} WHERE id = {class_id} AND teacher_id = {session['id']}')
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('home'))

classes = []
@app.route("/h_attendance")
def attendance():
    if len(session.values()) == 0:
         return render_template("login.html")
    global stop_event
    global classes
    stop_event.clear()  # Clear any previous stop signal
    threading.Thread(target=generate_frames).start()
    con=get_db_connection()
    cursor = con.cursor(dictionary=True)
    cursor.execute(f"select class_name,class_strength from class_data where teacher_id = '{session['id']}';")
    classes = cursor.fetchall()
    return render_template("h_attendance.html" , username=session['name'] , list=attendancelist ,classlist=classes ,flag=False ,curclass="-1")


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route("/h_students",methods=['GET','POST'])
def students():
    if len(session.values()) == 0:
        return render_template("login.html")
    
    con=get_db_connection()
    cursor = con.cursor(dictionary=True)
    cursor.execute(f"select class_name from class_data where teacher_id = '{session['id']}';")
    classes = cursor.fetchall()

    class_dirs = []
    # class_dirs = [d for d in os.listdir(app.config['UPLOAD_FOLDER']) if os.path.isdir(os.path.join(app.config['UPLOAD_FOLDER'], d))]
    for x in classes:
        for y in x.values():
            class_dirs.append(y)
    print(class_dirs)
    
    if request.method == 'POST':
        class_name = request.form.get('class_name')
        if 'files[]' not in request.files:
            print('No file part')
            return redirect(request.url)
        files = request.files.getlist('files[]')
        for file in files:
            if file.filename == '':
                print('No selected file')
                return redirect(request.url)
            if file and allowed_file(file.filename):
                filename = file.filename
                class_dir = os.path.join(app.config['UPLOAD_FOLDER'], class_name)
                if not os.path.exists(class_dir):
                    os.makedirs(class_dir)
                file.save(os.path.join(class_dir, filename))
            else:
                print("Incorrect file format")
        print('Files successfully uploaded')
        return redirect(url_for('students', class_name=class_name))
    
    selected_class = request.args.get('class_name', class_dirs[0] if class_dirs else None)
    student_details = []
    if selected_class:
        student_dir = os.path.join(app.config['UPLOAD_FOLDER'], selected_class)
        for filename in os.listdir(student_dir):
            if allowed_file(filename):
                rollno, name = filename.rsplit('.', 1)[0].split('_', 1)
                student_details.append({'rollno': rollno, 'name': name, 'filename': filename})
    
    return render_template('h_students.html', class_dirs=class_dirs, student_details=student_details, selected_class=selected_class)



@app.route("/h_manageclass")
def manage():
    camera.release()
    if len(session.values()) == 0:
         return render_template("login.html")
    attendancelist.clear()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(f'SELECT * FROM class_data WHERE teacher_id ={session['id']};')
    classes = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("h_manageclass.html" , username=session['name'],classes=classes)

@app.route('/add_classes', methods=['POST'])
def add_classes():
    if len(session.values()) == 0:
         return render_template("login.html")
    
    class_name = request.form['class_name']
    class_strength = request.form['class_strength']
    class_course = request.form['class_course']
    class_semester = request.form['class_semester']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"INSERT INTO class_data (teacher_id, class_name, class_strength, class_course, class_semester) VALUES ({session['id']}, '{class_name}', {class_strength}, '{class_course}', {class_semester});")
    conn.commit()
    cursor.close()
    conn.close()
    parent_dir = "static/classes/"
    directory = class_name
    path = os.path.join(parent_dir, directory) 
    if not os.path.exists(path):
        os.mkdir(path)
    return redirect(url_for('manage'))

@app.route('/edit_class/<int:class_id>', methods=['GET', 'POST'])
def edit_class(class_id):
    if len(session.values()) == 0:
         return render_template("login.html")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        class_name = request.form['class_name']
        class_strength = request.form['class_strength']
        class_course = request.form['class_course']
        class_semester = request.form['class_semester']
        cursor.execute('UPDATE class_data SET class_name = %s, class_strength = %s, class_course = %s, class_semester = %s WHERE class_id = %s AND teacher_id = %s',
                       (class_name, class_strength, class_course, class_semester, class_id, session['Id']))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('manage'))
    
    cursor.execute('SELECT * FROM class_data WHERE class_id = %s AND teacher_id = %s', (class_id, session['id']))
    class_data = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template('edit_class.html', class_data=class_data)

@app.route('/delete_class/<int:class_id>', methods=['POST'])
def delete_class(class_id):
    if len(session.values()) == 0:
         return render_template("login.html")

    conn = get_db_connection()
    cursor = conn.cursor()
    tempname = cursor.execute(f'select class_name from class_data WHERE class_id = {class_id} and teacher_id = {session['id']}')
    tempname = cursor.fetchone()
    print(tempname[0])
    cursor.execute('DELETE FROM class_data WHERE class_id = %s AND teacher_id = %s', (class_id, session['id']))
    conn.commit()
    cursor.close()
    conn.close()
    path = os.path.join('static/classes/', tempname[0]) 
    shutil.rmtree(path)

    return redirect(url_for('manage'))


@app.route("/h_myprofile")
def profile():
    if len(session.values()) == 0:
         return render_template("login.html")
    attendancelist.clear()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM login_data WHERE id = %s;', (session['id'],))
    teacher = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template("h_myprofile.html" , username=session['name'] , teacher=teacher)

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if len(session.values()) == 0:
         return render_template("login.html")

    name = request.form['name']
    email = request.form['email']
    password = request.form['password']
    confirm_password = request.form['confirm_password']

    if password != confirm_password:
        # Handle password mismatch error
        pass

    conn = get_db_connection()
    cursor = conn.cursor()
    if password:
        hashed_password = generate_password_hash(password)
        cursor.execute('UPDATE login_data SET name = %s, email = %s, password = %s WHERE id = %s',
                       (name, email, hashed_password, session['id']))
    else:
        cursor.execute('UPDATE login_data SET name = %s, email = %s WHERE id = %s',
                       (name, email, session['id']))
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('profile'))

@app.route("/logout")
def logout():
    camera.release()
    session.clear()
    return render_template("landing.html")

@app.route('/get_roll_numbers', methods=['GET'])
def get_roll_numbers():
    return jsonify(roll_numbers=attendancelist,length=len(attendancelist))


@app.route('/video')
def video():
    return Response(generate_frames(),mimetype='multipart/x-mixed-replace; boundary=frame')

class_name = ""
@app.route('/selected_class' , methods=['POST'])
def selected_class():
    global attendancelist
    global class_name
    attendancelist = []
    class_name = request.form['selectclass']
    if(class_name == "-1"):
        return render_template("h_attendance.html",username=session['name'] , list=attendancelist ,classlist=classes,flag=False ,class_name=class_name)
    else:
        return render_template("h_attendance.html",username=session['name'] , list=attendancelist ,classlist=classes,flag=True ,class_name=class_name)

camera=cv2.VideoCapture()
attendancelist = []
roll_numbers = []


@app.route('/stop_face_recognition')
def stop_face_recognition():
    global stop_event
    stop_event.set()  # Signal the thread to stop
    return jsonify({'status': 'Face recognition stopped'})

def generate_frames():
    known_face_encodings = []
    known_face_names = []   

    for imagepath in os.listdir(f'static/classes/{class_name}'):
        temp = imagepath.split('_')
        roll_numbers.append(temp[0])
        known_face_names.append(temp[1].split('.')[0])
        known_person1_image = face_recognition.load_image_file(f'static/classes/{class_name}/{imagepath}')
        known_person1_encoding = face_recognition.face_encodings(known_person1_image)[0]
        known_face_encodings.append(known_person1_encoding)

    attendancelist.clear()
    camera=cv2.VideoCapture(0)
    while not stop_event.is_set(): 
        ## read the camera frame
        success,frame=camera.read()
        if not success:
            break
        else:
            face_locations = face_recognition.face_locations(frame)
            face_encodings = face_recognition.face_encodings(frame,face_locations)

            for(top,right,bottom,left), face_encodings in zip(face_locations,face_encodings):
                matches = face_recognition.compare_faces(known_face_encodings, face_encodings)
                name="Unknown"
                rn = '?'

                if True in matches:
                    first_match_index = matches.index(True)
                    name = known_face_names[first_match_index]
                    rn = roll_numbers[first_match_index]


                cv2.rectangle(frame,(left,top),(right,bottom),(0,255,0),2)
                cv2.putText(frame,f'Rno.{rn},{name}',(left,top-10),cv2.FONT_HERSHEY_DUPLEX,0.9,(0,255,0),2)
                
                if rn!='?' and not rn in attendancelist:    
                    attendancelist.append(rn)
        
            ret,buffer=cv2.imencode('.jpg',frame)
            frame=buffer.tobytes()

            yield(b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                
if __name__ == "__main__":
    app.run(debug=True)

