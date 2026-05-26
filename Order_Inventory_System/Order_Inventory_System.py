"""
    Order and Stock Management System - Project Flow:
    
1)  Initially, the admin account and sample products are written to SQLite.
2)  The main menu offers login, register, or exit options.
3)  Username / password validation is performed (username is case-insensitive).
4)  Admin → admin panel; Customer → customer panel.
5)  Admin: product listing (with stock), adding, deleting, price/stock update.
6)  Customer: product listing (without stock, with critical stock warning), add to cart, view cart, 
    checkout, order history.
7)  Stock control is only performed at the time of payment; if insufficient, the product
    is dropped from the cart and the payment is completed with the updated remaining amount.
8)  Every transaction is also saved to the logs.txt file.
"""

import sqlite3
import datetime

#  COLOR (ANSI Escape Codes)
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    GRAY    = "\033[90m"

    @staticmethod
    def paint(text: str, *codes) -> str:
        return "".join(codes) + text + Color.RESET


#  HELPER VISUAL FUNCTIONS
class Console:
    WIDTH = 62

    @staticmethod
    def header(text: str):
        line = "═" * Console.WIDTH
        print(Color.paint(f"\n╔{line}╗", Color.CYAN, Color.BOLD))
        print(Color.paint(f"║{text.center(Console.WIDTH)}║", Color.CYAN, Color.BOLD))
        print(Color.paint(f"╚{line}╝", Color.CYAN, Color.BOLD))

    @staticmethod
    def sub_header(text: str):
        line = "─" * Console.WIDTH
        print(Color.paint(f"\n┌{line}┐", Color.BLUE))
        print(Color.paint(f"  {text}", Color.BLUE, Color.BOLD))
        print(Color.paint(f"└{line}┘", Color.BLUE))

    @staticmethod
    def success(text: str):
        print(Color.paint(f"  {text}", Color.GREEN, Color.BOLD))

    @staticmethod
    def error(text: str):
        print(Color.paint(f"  {text}", Color.RED, Color.BOLD))

    @staticmethod
    def info(text: str):
        print(Color.paint(f"  {text}", Color.YELLOW))

    @staticmethod
    def warning(text: str):
        print(Color.paint(f"  {text}", Color.MAGENTA, Color.BOLD))

    @staticmethod
    def menu_row(number: str, text: str):
        num = Color.paint(f"  [{number}]", Color.CYAN, Color.BOLD)
        print(f"{num}  {text}")

    @staticmethod
    def divider():
        print(Color.paint("  " + "·" * (Console.WIDTH - 2), Color.GRAY))

    @staticmethod
    def table_header(columns: list, widths: list):
        Console.divider()
        row = ""
        for title, w in zip(columns, widths):
            row += Color.paint(f"  {title:<{w}}", Color.YELLOW, Color.BOLD)
        print(row)
        Console.divider()

    @staticmethod
    def table_row(values: list, widths: list, color=None):
        row = ""
        for value, w in zip(values, widths):
            text = f"  {str(value):<{w}}"
            row += Color.paint(text, color) if color else text
        print(row)

    @staticmethod
    def prompt(message: str) -> str:
        return input(Color.paint(f"\n  {message}: ", Color.WHITE, Color.BOLD))


#  LOG (TXT)
class LogManager:
    FILE = "logs.txt"   

    @staticmethod
    def write(username: str, action: str, details: str = ""):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = (f"[{timestamp}] | User: {username:<12} | "
               f"Action: {action:<28} | {details}\n")
        with open(LogManager.FILE, "a", encoding="utf-8") as f:
            f.write(row)


#  DATABASE (SQLite)
class DatabaseManager:
    DB_NAME = "order_inventory.db"

    def __init__(self):
        self.connection = sqlite3.connect(self.DB_NAME)
        self.cursor     = self.connection.cursor()
        self._create_tables()
        self._insert_default_data()

    def _create_tables(self):
        self.cursor.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT    UNIQUE NOT NULL,
                password TEXT    NOT NULL,
                role     TEXT    NOT NULL DEFAULT 'customer'
            );
            CREATE TABLE IF NOT EXISTS products (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                name  TEXT    UNIQUE NOT NULL,
                price REAL    NOT NULL,
                stock INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS orders (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                product  TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                total    REAL    NOT NULL,
                date     TEXT NOT NULL
            );
        """)
        self.connection.commit()

    def _insert_default_data(self):
        credentials = {
            "admin": {"password": "123",  "role": "admin"},
            "john": {"password": "1111", "role": "customer"},
            "jane":  {"password": "2222", "role": "customer"},
        }
        for username, info in credentials.items():
            self.cursor.execute(
                "INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)",
                (username, info["password"], info["role"])
            )
        sample_products = [
            ("Pen", 10.0, 100),
            ("Notebook", 25.0, 50),
            ("Eraser", 5.0, 75),
        ]
        for product in sample_products:
            self.cursor.execute(
                "INSERT OR IGNORE INTO products (name, price, stock) VALUES (?, ?, ?)", product
            )
        self.connection.commit()

    def close(self):
        self.connection.close()


#  USER CLASS
class User:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def login(self, username: str, password: str) -> dict | None:
        # Case-insensitive comparison using LOWER()
        self.db.cursor.execute(
            "SELECT username, password, role FROM users WHERE LOWER(username) = LOWER(?)", (username,)
        )
        record = self.db.cursor.fetchone()
        if record and record[1] == password:
            return {"username": record[0], "role": record[2]}
        return None

    def register(self, username: str, password: str) -> bool:
        try:
            self.db.cursor.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, 'customer')",
                (username, password)
            )
            self.db.connection.commit()
            return True
        except sqlite3.IntegrityError:
            return False


#  PRODUCT CLASS
class Product:
    CRITICAL_STOCK = 3

    def __init__(self, db: DatabaseManager):
        self.db = db

    def list_all(self) -> list[dict]:
        self.db.cursor.execute("SELECT id, name, price, stock FROM products ORDER BY name")
        return [
            {"id": r[0], "name": r[1], "price": r[2], "stock": r[3]}
            for r in self.db.cursor.fetchall()
        ]

    def find(self, name: str) -> dict | None:
        self.db.cursor.execute(
            "SELECT id, name, price, stock FROM products WHERE LOWER(name) = LOWER(?)", (name,)
        )
        r = self.db.cursor.fetchone()
        return {"id": r[0], "name": r[1], "price": r[2], "stock": r[3]} if r else None

    def add(self, name: str, price: float, stock: int) -> bool:
        try:
            self.db.cursor.execute(
                "INSERT INTO products (name, price, stock) VALUES (?, ?, ?)", (name, price, stock)
            )
            self.db.connection.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def delete(self, name: str) -> bool:
        self.db.cursor.execute(
            "DELETE FROM products WHERE LOWER(name) = LOWER(?)", (name,)
        )
        self.db.connection.commit()
        return self.db.cursor.rowcount > 0

    def update_price(self, name: str, new_price: float) -> bool:
        self.db.cursor.execute(
            "UPDATE products SET price = ? WHERE LOWER(name) = LOWER(?)", (new_price, name)
        )
        self.db.connection.commit()
        return self.db.cursor.rowcount > 0

    def update_stock(self, name: str, new_stock: int) -> bool:
        self.db.cursor.execute(
            "UPDATE products SET stock = ? WHERE LOWER(name) = LOWER(?)", (new_stock, name)
        )
        self.db.connection.commit()
        return self.db.cursor.rowcount > 0

    def decrease_stock(self, name: str, quantity: int) -> bool:
        product = self.find(name)
        if product and product["stock"] >= quantity:
            self.db.cursor.execute(
                "UPDATE products SET stock = stock - ? WHERE LOWER(name) = LOWER(?)", (quantity, name)
            )
            self.db.connection.commit()
            return True
        return False


#  CART CLASS
class Cart:
    """Data: {product_name: {"price": float, "quantity": int}}"""

    def __init__(self):
        self.items: dict[str, dict] = {}

    def add(self, product_name: str, price: float, quantity: int):
        if product_name in self.items:
            self.items[product_name]["quantity"] += quantity
        else:
            self.items[product_name] = {"price": price, "quantity": quantity}

    def remove(self, product_name: str, quantity: int) -> str:
        for key in list(self.items):
            if key.lower() == product_name.lower():
                current = self.items[key]["quantity"]
                if quantity >= current:
                    del self.items[key]
                    return "removed_completely"
                else:
                    self.items[key]["quantity"] -= quantity
                    return "decreased"
        return "not_found"

    def is_empty(self) -> bool:
        return len(self.items) == 0

    def get_total(self) -> float:
        return sum(v["price"] * v["quantity"] for v in self.items.values())

    def clear(self):
        self.items.clear()


#  ORDER CLASS
class Order:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def save(self, username: str, product_name: str, quantity: int, total: float):
        date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.db.cursor.execute(
            "INSERT INTO orders (username, product, quantity, total, date) "
            "VALUES (?, ?, ?, ?, ?)",
            (username, product_name, quantity, total, date_str)
        )
        self.db.connection.commit()

    def list_orders(self, username: str = None) -> list[dict]:
        if username:
            self.db.cursor.execute(
                "SELECT username, product, quantity, total, date FROM orders "
                "WHERE username = ? ORDER BY date DESC", (username,)
            )
        else:
            self.db.cursor.execute(
                "SELECT username, product, quantity, total, date FROM orders "
                "ORDER BY date DESC"
            )
        return [
            {"username": r[0], "product": r[1], "quantity": r[2],
             "total": r[3], "date": r[4]}
            for r in self.db.cursor.fetchall()
        ]


#  MAIN APPLICATION CLASS
class Application:
    def __init__(self):
        self.db          = DatabaseManager()
        self.user_mgr    = User(self.db)
        self.product_mgr = Product(self.db)
        self.order_mgr   = Order(self.db)
        self.active_user: dict | None = None
        self.cart        = Cart()

    def run(self):
        while True:
            Console.header("ORDER & STOCK MANAGEMENT SYSTEM")
            Console.menu_row("1", "Login")
            Console.menu_row("2", "Register New Customer")
            Console.menu_row("0", "Exit")
            Console.divider()
            choice = Console.prompt("Your choice")

            if choice == "1":
                self._login_screen()
            elif choice == "2":
                self._register_screen()
            elif choice == "0":
                Console.success("Program terminated. Goodbye!")
                self.db.close()
                break
            else:
                Console.error("Invalid choice!")

    def _login_screen(self):
        Console.sub_header("LOGIN")
        username = Console.prompt("Username")
        password = Console.prompt("Password")
        user = self.user_mgr.login(username, password)
        if user:
            Console.success(f"Welcome, {user['username']}! ({user['role'].upper()})")
            LogManager.write(username, "Logged In")
            self.active_user = user
            self.cart.clear()
            if user["role"] == "admin":
                self._admin_panel()
            else:
                self._customer_panel()
        else:
            Console.error("Invalid username or password!")
            LogManager.write(username, "Failed Login Attempt")

    def _register_screen(self):
        Console.sub_header("CREATE NEW ACCOUNT")
        username = Console.prompt("Username")
        password = Console.prompt("Password")
        if self.user_mgr.register(username, password):
            Console.success(f"Customer account '{username}' successfully created.")
            LogManager.write(username, "Account Created", "role=customer")
        else:
            Console.error("This username is already taken!")

    def _show_products_admin(self):
        products = self.product_mgr.list_all()
        if not products:
            Console.info("No products available in the system yet.")
            return
        Console.table_header(["#", "PRODUCT NAME", "PRICE ($)", "STOCK"], [4, 22, 14, 10])
        for i, p in enumerate(products, 1):
            stock_color = Color.RED if p["stock"] < 10 else Color.GREEN
            stock_text  = Color.paint(str(p["stock"]), stock_color, Color.BOLD)
            print(
                Color.paint(f"  {str(i):<4}", Color.GRAY) +
                f"{p['name']:<24}" +
                Color.paint(f"{p['price']:<16.2f}", Color.YELLOW) +
                stock_text
            )
        Console.divider()

    def _show_products_customer(self):
        products = self.product_mgr.list_all()
        if not products:
            Console.info("No products available in the system yet.")
            return
        critical_exists = any(0 < p["stock"] <= Product.CRITICAL_STOCK for p in products)
        if critical_exists:
            Console.table_header(["#", "PRODUCT NAME", "PRICE ($)", "STATUS"], [4, 24, 14, 18])
        else:
            Console.table_header(["#", "PRODUCT NAME", "PRICE ($)"], [4, 24, 14])
        for i, p in enumerate(products, 1):
            stock = p["stock"]
            row = (
                Color.paint(f"  {str(i):<4}", Color.GRAY) +
                f"{p['name']:<26}" +
                Color.paint(f"{p['price']:.2f} $", Color.YELLOW)
            )
            if critical_exists:
                if 0 < stock <= Product.CRITICAL_STOCK:
                    status = Color.paint(f"    ! Only {stock} left !", Color.RED, Color.BOLD)
                else:
                    status = ""
                row += status
            print(row)
        Console.divider()

    def _show_cart(self):
        if self.cart.is_empty():
            Console.info("Your cart is empty.")
            return
        Console.table_header(
            ["PRODUCT NAME", "UNIT PRICE", "QTY", "SUBTOTAL"],
            [22, 14, 8, 14]
        )
        for product_name, info in self.cart.items.items():
            subtotal = info["price"] * info["quantity"]
            Console.table_row(
                [product_name, f"{info['price']:.2f} $", info["quantity"], f"{subtotal:.2f} $"],
                [22, 14, 8, 14]
            )
        Console.divider()
        print(Color.paint(
            f"  {'GRAND TOTAL':<44}{self.cart.get_total():.2f} $",
            Color.GREEN, Color.BOLD
        ))
        Console.divider()

    def _checkout(self):
        username = self.active_user["username"]
        if self.cart.is_empty():
            Console.info("Your cart is empty, nothing to pay for.")
            return

        Console.sub_header("CHECKOUT")
        self._show_cart()
        confirm = Console.prompt("Confirm payment? (y/n)").strip().lower()
        if confirm != "y":
            Console.info("Payment cancelled.")
            return

        failed: list[str] = []
        successful:  list[str] = []
        paid_amount = 0.0

        for product_name, info in list(self.cart.items.items()):
            quantity = info["quantity"]
            price    = info["price"]
            if self.product_mgr.decrease_stock(product_name, quantity):
                total = price * quantity
                paid_amount += total
                self.order_mgr.save(username, product_name, quantity, total)
                LogManager.write(
                    username, "Order Created",
                    f"product={product_name}, qty={quantity}, total={total:.2f}"
                )
                successful.append(product_name)
            else:
                failed.append(product_name)

        print()
        if successful:
            Console.success("The following products were successfully ordered:")
            for s in successful:
                print(Color.paint(f"     - {s}", Color.GREEN))

        if failed:
            Console.warning("The following products could not be ordered due to insufficient stock:")
            for f in failed:
                print(Color.paint(f"     - {f}", Color.MAGENTA))

        if paid_amount > 0:
            print(Color.paint(
                f"\n  {'Total Paid':<44}{paid_amount:.2f} $",
                Color.GREEN, Color.BOLD
            ))

        self.cart.clear()

    def _admin_panel(self):
        while True:
            username = self.active_user["username"]
            Console.header(f"ADMIN PANEL  |  {username.upper()}")
            Console.menu_row("1", "List Products")
            Console.menu_row("2", "Add Product")
            Console.menu_row("3", "Delete Product")
            Console.menu_row("4", "Update Price")
            Console.menu_row("5", "Update Stock")
            Console.menu_row("6", "View All Orders")
            Console.menu_row("9", "Return to Main Menu")
            Console.menu_row("0", "Exit")
            Console.divider()
            choice = Console.prompt("Your choice")

            if choice == "1":
                Console.sub_header("PRODUCT LIST")
                self._show_products_admin()

            elif choice == "2":
                Console.sub_header("ADD PRODUCT")
                product_name = Console.prompt("Product Name")
                try:
                    price = float(Console.prompt("Price ($)"))
                    stock = int(Console.prompt("Stock Quantity"))
                except ValueError:
                    Console.error("Invalid value!")
                    continue
                if self.product_mgr.add(product_name, price, stock):
                    Console.success(f"'{product_name}' successfully added.")
                    LogManager.write(username, "Product Added",
                                     f"product={product_name}, price={price}, stock={stock}")
                else:
                    Console.error("This product already exists in the system!")

            elif choice == "3":
                Console.sub_header("DELETE PRODUCT")
                product_name = Console.prompt("Product Name to Delete")
                if self.product_mgr.delete(product_name):
                    Console.success(f"'{product_name}' deleted.")
                    LogManager.write(username, "Product Deleted", f"product={product_name}")
                else:
                    Console.error("Product not found!")

            elif choice == "4":
                Console.sub_header("UPDATE PRICE")
                product_name = Console.prompt("Product Name")
                try:
                    new_price = float(Console.prompt("New Price ($)"))
                except ValueError:
                    Console.error("Invalid value!")
                    continue
                if self.product_mgr.update_price(product_name, new_price):
                    Console.success(f"'{product_name}' price updated -> {new_price:.2f} $")
                    LogManager.write(username, "Price Updated",
                                     f"product={product_name}, new_price={new_price}")
                else:
                    Console.error("Product not found!")

            elif choice == "5":
                Console.sub_header("UPDATE STOCK")
                product_name = Console.prompt("Product Name")
                try:
                    new_stock = int(Console.prompt("New Stock Quantity"))
                except ValueError:
                    Console.error("Invalid value!")
                    continue
                if self.product_mgr.update_stock(product_name, new_stock):
                    Console.success(f"'{product_name}' stock updated -> {new_stock}")
                    LogManager.write(username, "Stock Updated",
                                     f"product={product_name}, new_stock={new_stock}")
                else:
                    Console.error("Product not found!")

            elif choice == "6":
                Console.sub_header("ALL ORDERS")
                orders = self.order_mgr.list_orders()
                if not orders:
                    Console.info("No orders found in the system yet.")
                else:
                    Console.table_header(
                        ["USER", "PRODUCT", "QTY", "TOTAL($)", "DATE"],
                        [12, 14, 6, 13, 20]
                    )
                    grand_total = 0.0
                    for o in orders:
                        Console.table_row(
                            [o["username"], o["product"], o["quantity"],
                             f"{o['total']:.2f}", o["date"]],
                            [12, 14, 6, 13, 20]
                        )
                        grand_total += o["total"]
                    Console.divider()
                    print(Color.paint(
                        f"  {'TOTAL OF ALL ORDERS':<45}{grand_total:.2f} $",
                        Color.GREEN, Color.BOLD
                    ))
                    Console.divider()

            elif choice == "9":
                Console.info("Returning to main menu...")
                break
            elif choice == "0":
                Console.success("Closing application.")
                self.db.close()
                exit()
            else:
                Console.error("Invalid choice!")

    def _customer_panel(self):
        username = self.active_user["username"]
        while True:
            cart_summary = (
                Color.paint(
                    f"  Cart: {len(self.cart.items)} products  |  "
                    f"{self.cart.get_total():.2f} $",
                    Color.MAGENTA, Color.BOLD
                ) if not self.cart.is_empty() else ""
            )

            Console.header(f"CUSTOMER PANEL  |  {username.upper()}")
            if cart_summary:
                print(cart_summary)
            Console.menu_row("1", "List Products")
            Console.menu_row("2", "Add to Cart")
            Console.menu_row("3", "View Cart")
            Console.menu_row("4", "Remove Product from Cart")
            Console.menu_row("5", "Checkout")
            Console.menu_row("6", "My Order History")
            Console.menu_row("9", "Return to Main Menu")
            Console.menu_row("0", "Exit")
            Console.divider()
            choice = Console.prompt("Your choice")

            if choice == "1":
                Console.sub_header("PRODUCT LIST")
                self._show_products_customer()

            elif choice == "2":
                Console.sub_header("ADD TO CART")
                self._show_products_customer()
                product_name = Console.prompt("Product Name")
                product = self.product_mgr.find(product_name)
                if not product:
                    Console.error("Product not found!")
                    continue
                if product["stock"] <= 0:
                    Console.warning(f"'{product['name']}' is currently out of stock.")
                    continue
                try:
                    quantity = int(Console.prompt("How many would you like to add?"))
                    if quantity <= 0:
                        raise ValueError
                except ValueError:
                    Console.error("Invalid quantity!")
                    continue
                self.cart.add(product["name"], product["price"], quantity)
                Console.success(
                    f"'{product['name']}' x{quantity} added to cart.  "
                    f"(Cart total: {self.cart.get_total():.2f} $)"
                )

            elif choice == "3":
                Console.sub_header("MY CART")
                self._show_cart()

            elif choice == "4":
                Console.sub_header("REMOVE PRODUCT FROM CART")
                self._show_cart()
                if self.cart.is_empty():
                    continue
                product_name = Console.prompt("Product Name to Remove")

                matched = next(
                    (k for k in self.cart.items if k.lower() == product_name.lower()),
                    None
                )
                if matched is None:
                    Console.error("This product is not in your cart!")
                    continue

                current_quantity = self.cart.items[matched]["quantity"]
                Console.info(f"Current quantity of '{matched}' in your cart: {current_quantity}")

                try:
                    remove_quantity = int(Console.prompt(
                        f"How many would you like to remove? (enter {current_quantity} for all)"
                    ))
                    if remove_quantity <= 0:
                        raise ValueError
                except ValueError:
                    Console.error("Invalid quantity!")
                    continue

                result = self.cart.remove(product_name, remove_quantity)
                if result == "decreased":
                    remaining = self.cart.items[matched]["quantity"]
                    Console.success(
                        f"{remove_quantity} units of '{matched}' removed.  "
                        f"(Remaining: {remaining})"
                    )
                elif result == "removed_completely":
                    Console.success(f"'{matched}' completely removed from cart.")
                else:
                    Console.error("This product is not in your cart!")

            elif choice == "5":
                self._checkout()

            elif choice == "6":
                Console.sub_header("MY ORDER HISTORY")
                orders = self.order_mgr.list_orders(username=username)
                if not orders:
                    Console.info("You haven't placed any orders yet.")
                else:
                    Console.table_header(
                        ["PRODUCT", "QTY", "TOTAL($)", "DATE"],
                        [18, 6, 14, 22]
                    )
                    for o in orders:
                        Console.table_row(
                            [o["product"], o["quantity"],
                             f"{o['total']:.2f}", o["date"]],
                            [18, 6, 14, 22]
                        )
                    Console.divider()

            elif choice == "9":
                if not self.cart.is_empty():
                    Console.warning("You have products in your cart! Leaving will clear your cart.")
                    confirm = Console.prompt("Do you still want to leave? (y/n)").strip().lower()
                    if confirm != "y":
                        continue
                    self.cart.clear()
                Console.info("Returning to main menu...")
                break

            elif choice == "0":
                Console.success("Closing application.")
                self.db.close()
                exit()
            else:
                Console.error("Invalid choice!")


#  START
if __name__ == "__main__":
    app = Application()
    app.run()