from book_crawler.bookstores.Bookstores import Bookstores
from book_framework.DatabaseManager import DatabaseManager

#
# PRINTRE_CARTI = "/istorie-si-geografie/istorie/?p=%s"
# ANTICARIAT_UNU = "https://www.anticariat-unu.ro/istorie-c3/%s"

# TODO need a smart way to run the getters
if __name__ == '__main__':
    db_manager = DatabaseManager()

    # TODO - resetting the db after populating with older titles its a waste, need a way to only add new items,
    # TODO - full database refresh needs to be done, but not every run of the script
    bookstores = Bookstores(db_manager)
    bookstores.get_books()
