import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
import matplotlib
matplotlib.use('Agg') # Necessary for running Matplotlib on a web server
import matplotlib.pyplot as plt

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expenses.db'
app.config['SECRET_KEY'] = 'supersecretkey' 
db = SQLAlchemy(app)

# --- DATABASE MODELS ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    expenses = db.relationship('Expense', backref='owner', lazy=True)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

with app.app_context():
    db.create_all()

# --- HELPER: GRAPH LOGIC ---
def generate_weekly_chart(user_id):
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    daily_sums = {day: 0 for day in days}

    one_week_ago = datetime.utcnow() - timedelta(days=7)
    expenses = Expense.query.filter(
        Expense.user_id == user_id, 
        Expense.date >= one_week_ago
    ).all()

    if not expenses: 
        return False

    for e in expenses:
        day_name = e.date.strftime("%a") 
        if day_name in daily_sums:
            daily_sums[day_name] += e.amount

    plt.figure(figsize=(6, 4))
    bars = plt.bar(days, [daily_sums[d] for d in days], color='#bdd1f6')
    
    # Highlight today
    today_index = datetime.now().weekday()
    bars[today_index].set_color('#0055ff')

    # Clean styling
    plt.gca().spines['top'].set_visible(False)
    plt.gca().spines['right'].set_visible(False)
    plt.ylabel('Spending ($)')
    
    if not os.path.exists('static'): 
        os.makedirs('static')
    
    path = f'static/chart_{user_id}.png'
    plt.savefig(path, transparent=True)
    plt.close()
    return True

# --- ROUTES ---

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_expenses = Expense.query.filter_by(user_id=session['user_id']).all()
    total = sum(e.amount for e in user_expenses)
    has_chart = generate_weekly_chart(session['user_id']) 
    
    # Time-based calculations
    week_ago = datetime.utcnow() - timedelta(days=7)
    weekly_total = sum(e.amount for e in user_expenses if e.date >= week_ago)

    month_ago = datetime.utcnow() - timedelta(days=30)
    monthly_total = sum(e.amount for e in user_expenses if e.date >= month_ago)

    return render_template('index.html', 
                           expenses=user_expenses, 
                           total=total, 
                           weekly_total=weekly_total,
                           monthly_total=monthly_total,
                           has_chart=has_chart)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user_id'] = user.id
            return redirect(url_for('index'))
        return "Invalid Credentials. <a href='/login'>Try again</a>"
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        # Check if user exists
        existing_user = User.query.filter_by(username=request.form['username']).first()
        if existing_user:
            return "Username taken. <a href='/signup'>Try another</a>"
            
        new_user = User(username=request.form['username'], password=request.form['password'])
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/add', methods=['POST'])
def add_expense():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    new_ex = Expense(item=request.form['item'], 
                     amount=float(request.form['amount']), 
                     user_id=session['user_id'])
    db.session.add(new_ex)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))


@app.route('/delete/<int:id>')
def delete(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    expense_to_delete = Expense.query.get_or_404(id)
    # Security: Ensure only the owner can delete their own expense
    if expense_to_delete.user_id == session['user_id']:
        db.session.delete(expense_to_delete)
        db.session.commit()
    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(debug=True)