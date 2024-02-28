from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from openforms.accounts.tests.factories import (
    StaffUserFactory,
    TokenFactory,
    UserFactory,
)
from openforms.forms.tests.factories import CategoryFactory, FormFactory


class TestPublicFormEndpoint(APITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = StaffUserFactory.create()

        blue_cat = CategoryFactory.create(name="Blue")
        red_cat = CategoryFactory.create(name="Red")

        FormFactory.create(slug="deleted-form", deleted_=True)
        FormFactory.create(slug="1-form", category=blue_cat)
        FormFactory.create(slug="2-form", category=blue_cat)
        FormFactory.create(slug="3-form", category=red_cat)

    def test_cant_access_without_token(self):
        response = self.client.get(
            reverse(
                "api:public:forms:forms-list",
            )
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cant_access_without_being_staff(self):
        user = UserFactory.create()
        token = TokenFactory(user=user)

        response = self.client.get(
            reverse(
                "api:public:forms:forms-list",
            ),
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_deleted_forms_not_included(self):
        token = TokenFactory(user=self.user)

        response = self.client.get(
            reverse(
                "api:public:forms:forms-list",
            ),
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 3)

    def test_filter_on_category_name(self):
        token = TokenFactory(user=self.user)

        response = self.client.get(
            reverse(
                "api:public:forms:forms-list",
            ),
            data={"category__name": "Blue"},
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)
