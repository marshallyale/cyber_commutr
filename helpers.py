import secrets
import string


def generate_random_string(length=10):
    # Define the characters you want to include in the random string
    characters = (
        string.ascii_letters + string.digits
    )  # You can add more characters if needed

    # Generate a random string using the defined characters
    random_string = "".join(secrets.choice(characters) for _ in range(length))

    return random_string
