from server import Server
from utilities import format_res, format_res_err
from constants import IS_LOCAL
from classes import Traveller

from random import choice
from string import digits, ascii_letters, ascii_uppercase

from email_validator import validate_email, EmailNotValidError
from bcrypt import checkpw, gensalt, hashpw

MIN_ACCOUNT_NAME = 3
MAX_ACCOUNT_NAME = 20
MIN_PASS_LENGTH = 8
MAX_PASS_LENGTH = 20

class AccountHandler():
  """This handles anything to do with travellers and their accounts"""

  server: Server

  def __init__(self, server: Server):
    self.server = server
    if IS_LOCAL:
      travellers: dict[str, Traveller] = {}

    @server.register
    async def total_travellers(wss, event, ref):
      """Get the total number of travellers"""
      # TODO: Return total travellers
      return format_res('totalTravellers', ref, totalTravellers=0)

    @server.register
    async def fetch_travellers(wss, event, ref):
      """List all traveller ids"""
      # TODO: Return traveller ids
      return format_res('fetchTravellers', ref, travellerIds=[])
    
    @server.register
    async def create_traveller(wss, event, ref, traveller_name: str, traveller_email: str, traveller_password: str):
      """Creates a new traveller account.

      Args:
          traveller_name (str): The name of the traveller.
          traveller_email (str): The email of the traveller.
          traveller_password (str): The password of the traveller.
          wss (WebSocketClientProtocol): The websocket client.

      Possible Responses:
          createTravellerReply: The websocket has successfully created a traveller. No additional hashes have to be passed for future account-related methods.

          createTravellerEmailInvalid: The provided email is not formatted correctly.
          createTravellerEmailInUse: The provided email is already in use.
          createTravellerNameExceedsLimit: The provided name exceeds the current name length limitations.
          createTravellerPasswordExceedsLimit: The provided password exceeds the current password length limitations.
          createTravellerAlreadyLoggedIn: The IP is already logged in to another account.
          createTravellerMaxAccouns: The IP has created the maximum amount of accounts available.
      """

      if self.check_account(wss.remote_address[0]):
              return format_res_err(event, 'AlreadyLoggedIn', 'You are currently logged in. Logout and try again.', ref)

      """ Remember to keep the strip methods, we need the original name. """
      if not len(traveller_name.strip()) >= MIN_ACCOUNT_NAME or not len(traveller_name.strip()) <= MAX_ACCOUNT_NAME:
          return format_res_err(event, 'NameExceedsLimit', f'Traveller name must be between {MIN_ACCOUNT_NAME} and {MAX_ACCOUNT_NAME} characters long.', ref)

      """ Validate the email, check if it has @ and a valid domain. """
      try:
          validate_email(traveller_email)
      except EmailNotValidError as e:
          return format_res_err(event, 'EmailInvalid', str(e))

      if not len(traveller_password.strip()) >= MIN_PASS_LENGTH or not len(traveller_password.strip()) <= MAX_PASS_LENGTH:
          return format_res_err(event, 'PasswordExceedsLimit', f'Traveller password must be between {MIN_PASS_LENGTH} and {MAX_PASS_LENGTH} characters.', ref)

      """ Prevent duplicate emails. """
      is_email_taken = False

      if IS_LOCAL:
          for key, item in travellers.items():
              if item.traveller_email == traveller_email:
                  is_email_taken = True
                  break
      else:
          for key, item in self.get_users().items():
              if item['travellerEmail'] == traveller_email:
                  is_email_taken = True
                  break

      if is_email_taken:
          return format_res_err(event, 'EmailInUse', 'This email is already in use by another account.', ref)

      """ Visible by fetchTravellers and its not at all private. """
      traveller_id = self.gen_id()

      """ rounds=13 so as to exceed the 214ms bare limit according to: https://security.stackexchange.com/questions/3959/recommended-of-iterations-when-using-pkbdf2-sha256. """
      hashed_password = hashpw(bytes(traveller_password, encoding='ascii'), gensalt(rounds=13))

      if IS_LOCAL:
          travellers[traveller_id] = Traveller(traveller_id, traveller_name, traveller_email, hashed_password)
      else:
          self.server.mdb.users.insert_one({traveller_id: {'travellerName': traveller_name, 'travellerEmail': traveller_email,
                                              'travellerPassword': hashed_password}})

          """ Update registered emails and accounts links. """
      self.server.wss_accounts[wss.remote_address[0]] = traveller_id

      return format_res(event, ref, travellerId=traveller_id)

  def check_account(self, request_ip: str) -> bool:
    """Checks whether or not an IP is associated with an account.

    Args:
        request_ip (str): The IP of the request.

    Returns:
        bool: Whether or not it is linked to an account.
    """
    return request_ip in self.server.wss_accounts
  
  def gen_id(self) -> str:
    """Generates an ID with 15 digits for use when creating an account.

    Returns:
        str: The resulting ID.
    """
    result_id = ''

    for i in range(15):
        result_id += str(choice(f"{ascii_letters}{digits}"))

    return result_id
  
  def get_users(self) -> dict:
    """Returns the users which are created. Only for the database version.

    Returns:
        dict: The users dictionary.
    """

    result_users = {}

    """ Gets all ids in the users collection. """
    for cursor in self.server.mdb.users.find({}):
        del cursor['_id']
        result_users[list(cursor.keys())[0]] = list(cursor.values())[0]

    return result_users