#!/usr/bin/env python

# Licensed under the WTFPL license, http://sam.zoy.org/wtfpl/.

# std libs:
import argparse
import csv
import sys

# pypi libs:
import cairo
import pango
import pangocairo
from mysql import connector


__version__ = '0.1'

BADGE_HEIGHT = 76
BADGE_WIDTH = 100
PAGE_HEIGHT = 297
PAGE_WIDTH = 210
INNER_MARGIN = 5
TEXT_COLOR = (0, 0, 0)
DEFAULT_MYSQL_PORT = 3306


def convert_mm_to_dots(mm):
    return float(mm) / 25.4 * 72


def draw_text(ctx, pc, text, base_font_sz, y, text_width, text_height,
              area_width, multiline=False):
    font_sz = base_font_sz
    while font_sz > 6:
        name_fd = pango.FontDescription("DejaVu")
        name_fd.set_size(font_sz * pango.SCALE)
        layout = pc.create_layout()
        layout.set_font_description(name_fd)
        layout.set_text(text)
        layout.set_alignment(pango.ALIGN_CENTER)
        if multiline:
            layout.set_width(int(convert_mm_to_dots(text_width) * pango.SCALE))

        if layout.get_size()[0] > \
                (convert_mm_to_dots(text_width) * pango.SCALE):
            font_sz -= 1
            continue

        if layout.get_size()[1] > \
                (convert_mm_to_dots(text_height) * pango.SCALE):
            font_sz -= 1
            continue

        # draw
        text_x, text_y, text_w, text_h = layout.get_extents()[1]
        x = (convert_mm_to_dots(area_width) / 2) - \
            (text_w/2.0)/pango.SCALE - int(float(text_x)/pango.SCALE)
        y = y + (convert_mm_to_dots(text_height)/2) - \
            (text_h/2.0)/pango.SCALE - int(float(text_y)/pango.SCALE)
        ctx.move_to(x, y)
        pc.show_layout(layout)
        break


def draw_badge(ctx, width, height, description, background_image):
    im = cairo.ImageSurface.create_from_png(background_image)

    ctx.save()
    ctx.rectangle(0, 0, convert_mm_to_dots(width),
                  convert_mm_to_dots(height))
    ctx.scale(float(convert_mm_to_dots(width)) / im.get_width(),
              float(convert_mm_to_dots(height)) / im.get_height())
    ctx.set_source_surface(im)
    ctx.fill()
    ctx.restore()

    ctx.set_source_rgb(0.9, 0.9, 0.9)
    ctx.rectangle(0, 0, convert_mm_to_dots(width),
                  convert_mm_to_dots(height))
    ctx.stroke()

    if len(description) == 0:
        return

    name = description[0].strip()

    if len(description) > 1:
        company = description[1].strip()
    else:
        company = ''

    if len(description) > 2:
        role = description[2].strip()
    else:
        role = ''

    if name and company and role:
        name_y = 5
        company_y = 60
        role_y = 80
    elif name and company and not role:
        name_y = 10
        company_y = 70
    elif name and not company and role:
        name_y = 10
        role_y = 70
    elif name and not company and not role:
        name_y = 30

    ctx.set_source_rgb(TEXT_COLOR[0], TEXT_COLOR[1], TEXT_COLOR[2])
    pc = pangocairo.CairoContext(ctx)

    if name:
        draw_text(
            ctx, pc, name,    18, name_y, width * 0.9, height / 3, width, True)
    if company:
        draw_text(
            ctx, pc, company, 16, company_y, width * 0.9, height / 7, width)
    if role:
        draw_text(
            ctx, pc, role,    14, role_y, width * 0.9, height / 7, width)


def generate_document_from_csv(output_pdf, background_image, input_csv):
    return generate_document(
        badge_iterator=badges_from_csv(input_csv),
        output_pdf=output_pdf,
        background_image=background_image)


def generate_document_from_mysql(
        output_pdf, background_image, db_user, db_password, db_host, db_name,
        db_port=DEFAULT_MYSQL_PORT):
    return generate_document(
        badge_iterator=badges_from_mysql(
            db_user=db_user,
            db_password=db_password,
            db_name=db_name,
            db_host=db_host,
            db_port=db_port),
        output_pdf=output_pdf,
        background_image=background_image)


def generate_document(badge_iterator, output_pdf, background_image):
    surface = cairo.PDFSurface(output_pdf,
                               convert_mm_to_dots(PAGE_WIDTH),
                               convert_mm_to_dots(PAGE_HEIGHT))

    nb_badges_height = PAGE_HEIGHT / (BADGE_HEIGHT + INNER_MARGIN)
    nb_badges_width = PAGE_WIDTH / (BADGE_WIDTH + INNER_MARGIN)

    margin_top_bottom = (
        PAGE_HEIGHT -
        nb_badges_height * BADGE_HEIGHT -
        (nb_badges_height - 1) * INNER_MARGIN) / 2

    margin_left_right = (
        PAGE_WIDTH -
        nb_badges_width * BADGE_WIDTH -
        (nb_badges_width - 1) * INNER_MARGIN) / 2

    ctx = cairo.Context(surface)

    row = 0
    col = 0

    for badge in badge_iterator:
        ctx.save()
        ctx.translate(
            convert_mm_to_dots(
                margin_left_right + col * (BADGE_WIDTH + INNER_MARGIN)),
            convert_mm_to_dots(
                margin_top_bottom + row * (BADGE_HEIGHT + INNER_MARGIN))
            )
        draw_badge(ctx, BADGE_WIDTH, BADGE_HEIGHT, badge, background_image)
        ctx.restore()

        col += 1
        if col == nb_badges_width:
            col = 0
            row += 1
        if row == nb_badges_height:
            col = 0
            row = 0
            surface.show_page()

    surface.finish()


def badges_from_csv(csv_file):
    return csv.reader(open(csv_file, 'rb'), delimiter=',')


def badges_from_mysql(
        db_user, db_password, db_host, db_name, db_port=DEFAULT_MYSQL_PORT):
    try:
        connection = connector.connect(
            user=db_user,
            password=db_password,
            host=db_host,
            database=db_name,
            )
    except:
        print(
            'error attempting to connect to mysqldb using args:\n'
            'user: {}\n'
            'password: {}\n'
            'host: {}\n'
            'database name: {}\n'.format(
                db_user,
                db_password[0] + ('*' * (len(db_password) - 1)),
                db_host,
                db_name)
            )
        raise

    try:
        cursor = connection.cursor()

        cursor.execute('''
            SELECT
                fdcca.commerce_customer_address_name_line AS full_name
                , co.mail AS email
                , CASE
                    WHEN clt.line_item_label = 'conferencepass0th' THEN
                        'Conference Pass'
                    WHEN clt.line_item_label = 'trainingPass0th' THEN
                        'Training Pass'
                    WHEN clt.line_item_label = 'supporterpass0th' THEN
                        'Supporter Pass'
                  END AS pass_type
            FROM
                commerce_line_item AS clt
                INNER JOIN commerce_order AS co USING (order_id)
                INNER JOIN users AS u USING (uid)
                INNER JOIN (
                    SELECT
                        uid
                        , profile_id
                    FROM
                        commerce_customer_profile AS ccp
                    WHERE
                        profile_id = (
                            SELECT
                                max(profile_id)
                            FROM
                                commerce_customer_profile AS ccp2
                            WHERE
                                ccp.uid = ccp2.uid
                            )
                    ) subq USING (uid)
                INNER JOIN field_data_commerce_customer_address AS fdcca ON
                    subq.profile_id = fdcca.entity_id
            ''')

        for tuple in cursor:
            yield tuple
    finally:
        cursor.close()
        connection.close()


def main():
    parser = argparse.ArgumentParser(
        description=(
            'make printable badge pdfs for speakers & attendees of '
            'conferences')
        )
    parser.add_argument(
        '-b',
        dest='background_image',
        metavar='BACKGROUND_IMAGE',
        help='the location of the image file to use for badge backgrounds',
        )
    parser.add_argument(
        '-o',
        dest='output_pdf',
        metavar='OUTPUT_PDF',
        help='the location of the output pdf file')

    subparsers = parser.add_subparsers(dest='subparser_name')

    # for reading from csv:
    csv_parser = subparsers.add_parser(
        'from_csv', help='read user information from a csv file')
    csv_parser.add_argument(
        'input_csv',
        metavar='INPUT_CSV',
        help='the location of the input csv file')
    csv_parser.set_defaults(func=generate_document_from_csv)

    # for reading from mysql:
    mysql_parser = subparsers.add_parser(
        'from_mysql', help='read user information from a mysql db')
    mysql_parser.add_argument(
        'db_user',
        metavar='DATABASE_USER',
        help='the database user account')
    mysql_parser.add_argument(
        'db_password',
        metavar='DATABASE_PASSWORD',
        help='the password for the database')
    mysql_parser.add_argument(
        'db_host',
        metavar='DATABASE_HOST',
        help='the host of the database')
    mysql_parser.add_argument(
        'db_name',
        metavar='DATABASE_NAME',
        help='the name of the database')
    mysql_parser.add_argument(
        '--port',
        dest='db_port',
        metavar='DATABASE_PORT',
        default=DEFAULT_MYSQL_PORT,
        help='the port that the database server listens on')
    mysql_parser.set_defaults(func=generate_document_from_mysql)

    # for taking three args directly from the command line:
    direct_parser = subparsers.add_parser(
        'direct', help='take user info directly from the command line')
    direct_parser.add_argument(
        'user_name',
        metavar='USER_NAME',
        help='The user\'s  name, as it should appear prominently on the badge')
    direct_parser.add_argument(
        'nickname',
        metavar='NICK',
        help='The nickname/handle/twitter username of the user')
    direct_parser.add_argument(
        'pass_type',
        metavar='PASS_TYPE',
        help='The type of the pass')


    args = parser.parse_args()
    if args.subparser_name == 'from_csv':
        generate_document_from_csv(
            output_pdf=args.output_pdf,
            background_image=args.background_image,
            input_csv=args.input_csv)
    elif args.subparser_name == 'from_mysql':
        generate_document_from_mysql(
            output_pdf=args.output_pdf,
            background_image=args.background_image,
            db_user=args.db_user,
            db_password=args.db_password,
            db_host=args.db_host,
            db_name=args.db_name,
            db_port=args.db_port)
    elif args.subparser_name == 'direct':
        generate_document(
            badge_iterator=[(args.user_name, args.nickname, args.pass_type)],
            output_pdf=args.output_pdf,
            background_image=args.background_image,
            )
    else:
        raise NotImplementedError(
            'unrecognized subparser: {}'.format(args.subparser_name))

if __name__ == '__main__':
    sys.exit(main())
