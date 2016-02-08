import gzip
import json
import sys
import traceback
import webbrowser
from html import unescape
from io import BytesIO
from urllib.parse import quote_plus
from urllib.request import urlopen


def laze(func):
    def func_wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as ex:
            ignored_exception_types = [KeyboardInterrupt, KeyError, AttributeError]
            if type(ex) in ignored_exception_types:
                print("This exception is too simple to worth searching a solution...", file=sys.stderr)
                raise
            else:
                try:
                    # Get the last line of the exception message, as you always do
                    ex = traceback.format_exc().split("\n")[-2]

                    # name is the name of the exception's class, such as "xml.etree.ElementTree.ParseError"
                    # message is the explanation part that comes after the first colon
                    # module is the name of the module that exception belongs, such as "xml"
                    name, message = ex.split(":", maxsplit=1)
                    module = name.split(".")[0] if name.count(".") > 0 else None
                    message = strip_urls(strip_linecol(strip_names(strip_objects(message))))

                    # Print exception first so that programmer can miserably try debugging it himself/herself.
                    traceback.print_exc()
                    print(file=sys.stderr)

                    results = so_search(name + " " + message, tags=[module] if module else None)

                    user_interface(results)
                except:
                    print("\nI've got an exception while handling yours, but I'll not try debugging myself, for I "
                          "don't have such second order desires.\n",
                          file=sys.stderr)
                    raise

                exit(-1)

    return func_wrapper


def strip_objects(msg: str):
    """
    Removes
        <__main__.AClass object at 0x7f3082bb2fd0>

    messages.
    """

    while True:
        start = msg.find("<")
        if start == -1:
            break

        end = msg.find(">")

        if " object at " in msg[start:end + 1]:
            msg = msg.replace(msg[start:end + 1], "")

    return msg


def strip_names(msg: str):
    """
    Strip anything that is enclosed between single- or double quotes.

    Example:
        FATAL:  password authentication failed for user "bora"

        becomes

        FATAL:  password authentication failed for user
    """
    
    def strip_names_with(character: chr):
        nonlocal msg
        while True:
            start = msg.find(character)
            if start == -1:
                break
    
            end = msg.find(character, start + 1)
    
            if end - start >= 3:
                msg = msg.replace(msg[start:end + 1], "")
    
    strip_names_with('"')
    strip_names_with('\'')
    return msg


def strip_linecol(msg: str):
    """
    Strips line and column messages of exception occurrence.
    
    Example:
        json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)

        becomes

        json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes:
    """

    line = msg.find(" line ")
    column = msg.find(" column ")

    if column > line:
        msg = msg.replace(msg[line:], "")

    return msg


def strip_urls(msg: str):
    """
    Strips all urls from msg.
    
    Example:
        An error has raised while running a task due to AAA. Visit http://company.com for more info.
        
        becomes
        
        An error has raised while running a task due to AAA. Visit .
    """
    # colon slash slash

    while True:
        css = msg.find("://")
        if css == -1:
            break

        beginning = msg.rfind(" ", 0, css) + 1
        end = msg.find(" ", css)

        if end != -1:
            msg = msg.replace(msg[beginning:end], "")
        else:
            msg = msg.replace(msg[beginning:], "")

    return msg


def user_interface(results):
    """
    Simple interactive interface to show solutions from stackoverflow. A numbered
    list of links is shown, and entering a number (in range) causes your browser
    to open the chosen link. Quitting is possible by entering one of q, quit, e or exit.
    Pressing ^C quits and opens a page to ask a question on stackoverflow.
    """
    
    page = 0
    result_per_page = 10

    try:
        if not results:
            print("No results found", file=sys.stderr)
        else:
            print(len(results), "results found:", file=sys.stderr)

        do_not_print_again = False
        while True:
            page_content = results[result_per_page * page:  (page + 1) * result_per_page]
            if not page_content:
                break

            if not do_not_print_again:
                print("\tPage", page + 1, file=sys.stderr)
                for i, res in enumerate(page_content):
                    print("\t%d " % i, res["title"], file=sys.stderr)

                do_not_print_again = False

            print("\t? ", end="", file=sys.stderr)
            c = input()
            if c in ["q", "quit", "e", "exit"]:
                print(file=sys.stderr)
                break
            elif c == "":
                page += 1
                do_not_print_again = False
                print(file=sys.stderr)
                continue
            try:
                c = int(c)
            except ValueError:
                print("\nEnter a number between 0-{} or 'quit'.\n".format(len(results)-1), file=sys.stderr)
                continue

            if 0 <= int(c) < len(results):
                c = results[int(c) * (page + 1)]
                to_open = c.get("answer", c["link"])
                webbrowser.open(to_open, new=1)
                do_not_print_again = True
                continue
            else:
                print("\nEnter a number *between* 0, {}\n".format(len(results)-1 if len(results) > 1 else ""))

    except KeyboardInterrupt:
        webbrowser.open("https://stackoverflow.com/questions/ask", new=1)
        print("\n", file=sys.stderr)


def so_search(q, tags=None, accepted=None):
    """
    Searches for questions on stackoverflow by tags and returns it. Questions
    that get accepted answers are directly linked to it.
    """
    
    assert isinstance(q, str)
    assert isinstance(tags, (list, type(None)))
    assert isinstance(accepted, (bool, type(None)))

    if not tags:
        tags = []
    tags.append("python")

    while True:
        url = "https://api.stackexchange.com/2.2/search/advanced?order=desc&sort=relevance&q={}" \
              "{}&tagged={}&site=stackoverflow".format(quote_plus(q),
                                                       "&accepted=" + str(accepted) if accepted is not None else "",
                                                       ";".join(tags))
        response = urlopen(url)
        results = json.loads(gzip.GzipFile(fileobj=BytesIO(response.read())).read().decode("utf-8"))

        if len(tags) >= 2 and not results["items"]:
            # Because some idiots do not tag their questions properly
            tags = ["python"]
            continue
        else:
            break

    simple_results = []
    for result in results["items"]:
        rd = {"title": unescape(result["title"]),
              "link": result["link"]}
        if "accepted_answer_id" in result:
            rd["answer"] = "http://stackoverflow.com/a/" + str(result["accepted_answer_id"])

        simple_results.append(rd)

    return simple_results

@laze
def f():
    s = ""
    s.asas()

print(f())
