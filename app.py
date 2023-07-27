import os
from flask import Flask, flash, request, redirect, render_template, send_from_directory
from werkzeug.utils import secure_filename
import tempfile
import shutil
from flask_mail import Mail, Message
from checking import *

ALLOWED_EXTENSIONS = set(['cnv', 'xml'])

app = Flask(__name__, template_folder='templates')

app.config.from_pyfile('config.py')

mail = Mail(app)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    

@app.route('/')
def step1():
    tmpdir = tempfile.mkdtemp()
    app.config['UPLOAD_FOLDER'] = tmpdir
    print("temporary directory at " + tmpdir)
    if not os.path.exists(tmpdir):          
        os.makedirs(tmpdir) 
    return render_template('step1.html')


@app.route('/step2')
def step2(): 
    return render_template('step2.html')

@app.route('/step2B')
def step2B(): 
    return render_template('step2B.html')    

@app.route('/step3')
def step3(): 
    return render_template('step3.html') 

@app.route('/', methods=['GET', 'POST'])
def upload_csr_file():    
    if request.method == 'POST':
        
        #Options are obtained from html template as list object
        option = request.form.getlist('option')
        print('Option: ', option)

        if option == ['1']:
            if 'files[]' not in request.files:
                flash("No file part", "Error")
                return redirect(request.url)            
        elif option == ['2'] or option == ['3'] or option == ['4']:
            if 'file' not in request.files and 'files[]' not in request.files:
                flash("No file part", "Error")
                return redirect(request.url)            
        else:
            flash("Something was wrong when selecting option", "Error")
            return redirect(request.url)
        
        uploaded_csr = False              
        if option == ['2'] or option == ['3'] or option == ['4']:
            file_csr = request.files['file']        
            if file_csr.filename == '':
                flash("No files selected for uploading", "Error")
                return redirect(request.url)
            if file_csr and allowed_file(file_csr.filename):
                filename = secure_filename(file_csr.filename)
                file_csr.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                uploaded_csr = True
                print("Parse CSR. Upload Folder: " + app.config['UPLOAD_FOLDER'])
                csr = load_csr(app.config['UPLOAD_FOLDER'])
            else:
                flash("Allowed file type is xml", "warning")
                return redirect(request.url)
        
        uploaded_cnv = False
        files = request.files.getlist('files[]')        
        for file in files:
            if file and allowed_file(file.filename):                
                filename = secure_filename(file.filename)            
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                uploaded_cnv = True
               
        if(uploaded_csr is True and uploaded_cnv is True):
            print('Process CTDs and CSR')
            if option == ['2']:
                metadata = check_casts(app.config['UPLOAD_FOLDER'], csr, tonetcdf = False, merged_ncfile = False)
            elif option == ['3']:
                metadata = check_casts(app.config['UPLOAD_FOLDER'], csr, tonetcdf = True, merged_ncfile = False)
            else:
                metadata = check_casts(app.config['UPLOAD_FOLDER'], csr, tonetcdf = True, merged_ncfile = True)
            #return render_template('step2.html', success='True')
        elif(uploaded_csr is False and uploaded_cnv is True):
            print('Process only CTDS')
            metadata = check_casts(app.config['UPLOAD_FOLDER'])
            #return render_template('step2.html', success='False')
        else:
            flash("Files were not uploaded", "warning")        
            return redirect(request.url)
        
        if metadata:
            route = []
            for idx, station in enumerate(metadata):
                shoredistance = metadata[idx]['shoredistance']
                name = metadata[idx]['name']
                lat = metadata[idx]['lat']
                lon = metadata[idx]['lon']
                time = metadata[idx]['time']
                bathymetry = metadata[idx]['bathymetry']
                depth = metadata[idx]['depth']
                if  shoredistance < 0 :
                    onland = 1
                else:
                    onland = 0
                adict={'name': name,
                       'lat': lat,           
                       'lon': lon,
                       'time': time,
                       'bathymetry': round(bathymetry),
                       'depth': depth,
                       'shoredistance': round(shoredistance/1000),
                       'onland': onland
                       }
                dictionary_copy = adict.copy()
                route.append(dictionary_copy)
                
            mean_lat = sum(d['lat'] for d in route) / len(route)   
            mean_lon = sum(d['lon'] for d in route) / len(route)
            mean_coords = [mean_lat, mean_lon]

            try:
                print('Sending mail')
                msg = Message('New CTD set processed', sender = app.config['MAIL_USERNAME'], recipients = app.config['MAIL_RECIPIENTS'])
                if csr:
                    msg.body = "Hi, survey " + csr["cruise_name"] + " with " + str(len(metadata)) + " CTDs has been processed."
                    
                else:
                    msg.body = "Hi, " + str(len(metadata)) + "CTDs with no metadata have been processed."
                mail.send(msg)
            except:
                pass

            
            return render_template('step2.html', COORDS=route, MEAN_COORDS=mean_coords)
            
        else:
            return redirect('/step2B')
 

@app.route('/return-files/')
def return_files_tut():
    try:
        archive_name = 'CTD_checked'        
        shutil.make_archive(archive_name, 'zip', app.config['UPLOAD_FOLDER'], 'ctdcheck_output')
        shutil.move('%s.%s'%(archive_name,'zip'), app.config['UPLOAD_FOLDER'])
        return send_from_directory(app.config['UPLOAD_FOLDER'], archive_name + '.zip', as_attachment=True, cache_timeout=0)
    except Exception as e:
        return str(e)

@app.route('/return-test/')
def return_files_test():
    try:        
        return send_from_directory('./tests/', 'test_download.zip', as_attachment=True, cache_timeout=0)
    except Exception as e:
        return str(e)
        

if __name__ == "__main__":
    (app.run(host = '0.0.0.0', debug=True))
