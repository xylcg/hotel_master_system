from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime
from models import db, User, Room, Order, Comment
from config import Config
import os
from functools import wraps
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# 创建上传文件夹
if not os.path.exists('static/images'):
    os.makedirs('static/images')


# 辅助函数 - 使用wraps保持函数名
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('需要管理员权限', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


# 前台路由
@app.route('/')
def index():
    rooms = Room.query.filter_by(status='available').all()
    return render_template('front/index.html', rooms=rooms)


@app.route('/room/<int:room_id>')
def room_detail(room_id):
    room = Room.query.get_or_404(room_id)
    comments = Comment.query.filter_by(room_id=room_id).order_by(Comment.created_at.desc()).all()
    return render_template('front/room.html', room=room, comments=comments)


@app.route('/book/<int:room_id>', methods=['GET', 'POST'])
@login_required
def book_room(room_id):
    room = Room.query.get_or_404(room_id)

    if request.method == 'POST':
        try:
            check_in = datetime.strptime(request.form['check_in'], '%Y-%m-%d')
            check_out = datetime.strptime(request.form['check_out'], '%Y-%m-%d')
            days = (check_out - check_in).days

            if days <= 0:
                flash('退房日期必须晚于入住日期', 'danger')
                return redirect(url_for('room_detail', room_id=room_id))

            total_price = room.price * days

            order = Order(
                room_id=room_id,
                user_id=session['user_id'],
                check_in=check_in,
                check_out=check_out,
                total_price=total_price
            )

            db.session.add(order)
            db.session.commit()

            flash('预订成功!', 'success')
            return redirect(url_for('my_orders'))

        except ValueError:
            flash('日期格式不正确', 'danger')

    return render_template('front/book.html', room=room)


@app.route('/my-orders')
@login_required
def my_orders():
    orders = Order.query.filter_by(user_id=session['user_id']).order_by(Order.created_at.desc()).all()
    return render_template('front/orders.html', orders=orders)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username, password=password).first()

        if user:
            session['user_id'] = user.id
            session['role'] = user.role
            flash('登录成功', 'success')

            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('index'))
        else:
            flash('用户名或密码错误', 'danger')

    return render_template('front/login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        phone = request.form['phone']

        if User.query.filter_by(username=username).first():
            flash('用户名已存在', 'danger')
            return redirect(url_for('register'))

        user = User(
            username=username,
            password=password,
            email=email,
            phone=phone
        )

        db.session.add(user)
        db.session.commit()

        flash('注册成功，请登录', 'success')
        return redirect(url_for('login'))

    return render_template('front/register.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('已退出登录', 'info')
    return redirect(url_for('index'))


# 后台路由
@app.route('/admin')
@admin_required
def admin_dashboard():
    stats = {
        'total_rooms': Room.query.count(),
        'available_rooms': Room.query.filter_by(status='available').count(),
        'occupied_rooms': Room.query.filter_by(status='occupied').count(),
        'total_orders': Order.query.count(),
        'pending_orders': Order.query.filter_by(status='pending').count()
    }
    return render_template('back/dashboard.html', stats=stats)


@app.route('/admin/rooms')
@admin_required
def admin_rooms():
    rooms = Room.query.all()
    return render_template('back/rooms.html', rooms=rooms)


@app.route('/admin/orders')
@admin_required
def admin_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('back/orders.html', orders=orders)


@app.route('/admin/users')
@admin_required
def admin_users():
    users = User.query.all()
    return render_template('back/users.html', users=users)


# 允许的文件扩展名
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/admin/room/add', methods=['GET', 'POST'])
@admin_required
def admin_add_room():
    if request.method == 'POST':
        try:
            name = request.form['name']
            price = float(request.form['price'])
            room_type = request.form['type']
            capacity = int(request.form['capacity'])
            description = request.form['description']

            # 初始化图片为默认值
            image_filename = 'default.jpg'

            # 处理文件上传
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename != '':
                    # 确保是允许的文件类型
                    if allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        image_filename = f"room_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                        file.save(os.path.join('static/images', image_filename))
                    else:
                        flash('只允许上传图片文件 (png, jpg, jpeg, gif)', 'warning')

            # 创建房间记录
            room = Room(
                name=name,
                price=price,
                type=room_type,
                capacity=capacity,
                description=description,
                image=image_filename,  # 使用默认或上传的文件名
                status='available'
            )

            db.session.add(room)
            db.session.commit()

            flash('客房添加成功', 'success')
            return redirect(url_for('admin_rooms'))

        except Exception as e:
            db.session.rollback()
            flash(f'添加失败: {str(e)}', 'danger')
            app.logger.error(f'添加客房失败: {str(e)}')

    return render_template('back/add_room.html')


# 编辑客房
@app.route('/admin/room/edit/<int:room_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_room(room_id):
    room = Room.query.get_or_404(room_id)

    if request.method == 'POST':
        try:
            room.name = request.form['name']
            room.price = float(request.form['price'])
            room.type = request.form['type']
            room.capacity = int(request.form['capacity'])
            room.description = request.form['description']

            # 处理文件上传
            if 'image' in request.files:
                file = request.files['image']
                if file.filename != '':
                    # 删除旧图片
                    if room.image and os.path.exists(os.path.join('static/images', room.image)):
                        os.remove(os.path.join('static/images', room.image))

                    filename = f"room_{datetime.now().strftime('%Y%m%d%H%M%S')}.{file.filename.split('.')[-1]}"
                    file.save(os.path.join('static/images', filename))
                    room.image = filename

            db.session.commit()

            flash('客房信息更新成功', 'success')
            return redirect(url_for('admin_rooms'))

        except Exception as e:
            flash(f'更新失败: {str(e)}', 'danger')

    return render_template('back/edit_room.html', room=room)


# 删除客房
@app.route('/admin/room/delete/<int:room_id>', methods=['POST'])
@admin_required
def admin_delete_room(room_id):
    room = Room.query.get_or_404(room_id)

    try:
        # 删除关联订单和评论
        Order.query.filter_by(room_id=room_id).delete()
        Comment.query.filter_by(room_id=room_id).delete()

        # 删除图片文件
        if room.image and os.path.exists(os.path.join('static/images', room.image)):
            os.remove(os.path.join('static/images', room.image))

        db.session.delete(room)
        db.session.commit()

        flash('客房删除成功', 'success')
    except Exception as e:
        flash(f'删除失败: {str(e)}', 'danger')

    return redirect(url_for('admin_rooms'))


@app.route('/admin/user/delete/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)

    # 防止删除当前登录的管理员账户
    if user.id == session.get('user_id'):
        flash('不能删除当前登录的管理员账户', 'danger')
        return redirect(url_for('admin_users'))

    try:
        # 删除关联数据
        Order.query.filter_by(user_id=user_id).delete()
        Comment.query.filter_by(user_id=user_id).delete()

        db.session.delete(user)
        db.session.commit()

        flash('用户删除成功', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'删除失败: {str(e)}', 'danger')

    return redirect(url_for('admin_users'))


@app.route('/admin/order/status/<int:order_id>', methods=['POST'])
@admin_required
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')

    # 映射英文状态到中文
    status_mapping = {
        'pending': '待处理',
        'confirmed': '已确认',
        'cancelled': '已取消'
    }

    if new_status in status_mapping:
        order.status = status_mapping[new_status]
        db.session.commit()
        flash('订单状态更新成功', 'success')
    else:
        flash('无效的订单状态', 'danger')

    return redirect(url_for('admin_orders'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        # 创建默认管理员账户
        if not User.query.filter_by(role='admin').first():
            admin = User(
                username='admin',
                password='admin123',
                email='admin@hotel.com',
                phone='13800138000',
                role='admin'
            )
            db.session.add(admin)

            # 添加示例房间
            rooms = [
                Room(name='豪华大床房', price=599, type='大床房', capacity=2,
                     description='宽敞舒适的大床房，配备豪华设施', image='room1.jpg'),
                Room(name='标准双床房', price=399, type='双床房', capacity=2,
                     description='经济实惠的标准双床房', image='room2.jpg'),
                Room(name='行政套房', price=1299, type='套房', capacity=4,
                     description='豪华行政套房，适合商务人士', image='room3.jpg')
            ]
            db.session.add_all(rooms)
            db.session.commit()

    app.run(debug=True)