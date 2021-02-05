import unittest
from functools import wraps

from peewee import *

import tacocat
from models import User, Taco

TEST_DB = SqliteDatabase(':memory:')
TEST_DB.connect()
TEST_DB.create_tables([User, Taco], safe=True)

USER_DATA = {
    'email': 'test_0@example.com',
    'password': 'password'
}

MODELS = (User, Taco,)


# Bind the given models to the db for the duration of wrapped block.
def use_test_database(fn):
    @wraps(fn)
    def inner(self):
        with TEST_DB.bind_ctx(MODELS):
            TEST_DB.create_tables(MODELS)
            try:
                fn(self)
            finally:
                TEST_DB.drop_tables(MODELS)
    return inner


class UserModelTestCase(unittest.TestCase):
    @staticmethod
    def create_users(count=2):
        for i in range(count):
            User.create_user(
                email='test_{}@example.com'.format(i),
                password='password'
            )

    @use_test_database
    def test_create_user(self):
        self.create_users()
        self.assertEqual(User.select().count(), 2)
        self.assertNotEqual(
            User.select().get().password,
            'password'
        )

    @use_test_database
    def test_create_duplicate_user(self):
        self.create_users()
        with self.assertRaises(ValueError):
            User.create_user(
                email='test_1@example.com',
                password='password'
            )


class TacoModelTestCase(unittest.TestCase):
    @use_test_database
    def test_taco_creation(self):
        UserModelTestCase.create_users()
        user = User.select().get()
        Taco.create(
            user=user,
            protein='chicken',
            shell='flour',
            cheese=False,
            extras='Gimme some guac.'
        )
        taco = Taco.select().get()

        self.assertEqual(
            Taco.select().count(),
            1
        )
        self.assertEqual(taco.user, user)


class ViewTestCase(unittest.TestCase):
    def setUp(self):
        tacocat.app.config['TESTING'] = True
        tacocat.app.config['WTF_CSRF_ENABLED'] = False
        self.app = tacocat.app.test_client()


class UserViewsTestCase(ViewTestCase):
    @use_test_database
    def test_registration(self):
        data = {
            'email': 'test@example.com',
            'password': 'password',
            'password2': 'password'
        }
        rv = self.app.post(
            '/register',
            data=data)
        self.assertEqual(rv.status_code, 302)
        self.assertEqual(rv.location, 'http://localhost/')

    @use_test_database
    def test_good_login(self):
        UserModelTestCase.create_users(1)
        rv = self.app.post('/login', data=USER_DATA)
        self.assertEqual(rv.status_code, 302)
        self.assertEqual(rv.location, 'http://localhost/')

    @use_test_database
    def test_bad_login(self):
        rv = self.app.post('/login', data=USER_DATA)
        self.assertEqual(rv.status_code, 200)

    @use_test_database
    def test_logout(self):
        # Create and login the user
        UserModelTestCase.create_users(1)
        self.app.post('/login', data=USER_DATA)

        rv = self.app.get('/logout')
        self.assertEqual(rv.status_code, 302)
        self.assertEqual(rv.location, 'http://localhost/')

    @use_test_database
    def test_logged_out_menu(self):
        rv = self.app.get('/')
        self.assertIn("sign up", rv.get_data(as_text=True).lower())
        self.assertIn("log in", rv.get_data(as_text=True).lower())

    @use_test_database
    def test_logged_in_menu(self):
        UserModelTestCase.create_users(1)
        self.app.post('/login', data=USER_DATA)
        rv = self.app.get('/')
        self.assertIn("add a new taco", rv.get_data(as_text=True).lower())
        self.assertIn("log out", rv.get_data(as_text=True).lower())


class TacoViewsTestCase(ViewTestCase):
    @use_test_database
    def test_empty_db(self):
        rv = self.app.get('/')
        self.assertIn("no tacos yet", rv.get_data(as_text=True).lower())

    @use_test_database
    def test_taco_create(self):
        taco_data = {
            'protein': 'chicken',
            'shell': 'flour',
            'cheese': False,
            'extras': 'Gimme some guac.'
        }
        UserModelTestCase.create_users(1)
        self.app.post('/login', data=USER_DATA)

        taco_data['user'] = User.select().get()
        rv = self.app.post('/taco', data=taco_data)
        self.assertEqual(rv.status_code, 302)
        self.assertEqual(rv.location, 'http://localhost/')
        self.assertEqual(Taco.select().count(), 1)

    @use_test_database
    def test_taco_list(self):
        taco_data = {
            'protein': 'chicken',
            'shell': 'flour',
            'cheese': False,
            'extras': 'Gimme some guac.'
        }
        UserModelTestCase.create_users(1)
        taco_data['user'] = User.select().get()
        Taco.create(**taco_data)

        rv = self.app.get('/')
        self.assertNotIn('no tacos yet', rv.get_data(as_text=True))
        self.assertIn(taco_data['extras'], rv.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()