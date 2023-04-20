Peddle Perth Riders Website
===========================

Copyright (C) 2023 Peddle Perth Pty Ltd. See [LICENSE] for details.

## Info
Created thanks to the following open source software:

- [Django Web Framework](https://www.djangoproject.com/) and [Python](https://www.python.org/)
- [React JS](https://react.dev/)
- [Bootstrap](https://getbootstrap.com/)
- [React Bootstrap](https://react-bootstrap.netlify.app/)
- [jQuery](https://jquery.com/)

This repository provides a friendly website to manage rickshaw tour schedules and riders. Tour bookings are synchronised in real-time from multiple online sources including [Rezdy](https://rezdy.com/) and [Red61](https://www.red61.com/). Shifts and staff and rider details are synchronised with [Deputy](https://www.deputy.com) - with special thanks to the Deputy team for publishing an awesome API.

## Development
This software was developed on Linux and these instructions may not work on other platforms.

Main dev system requirements:

- Python 3.8 or above. (Check `python3 --version`)
- Ability to install packages from python's pip repository using `pip`
- Python virtualenv (`virtualenv` or `python3 -m virtualenv`)
- Node package manager `npm`
- Postgresql 13 or later, or you can use sqlite3 for development
- Docker - if you want to run postgresql in a docker container

Use a python virtualenv to install the python requirements (see requirements.txt, made using `pip freeze`).

```
npm run setupvenv # create python virtual env + add some django settings as environment variables
npm run initdb # init the docker postgres container
npm run startdb # start the docker postgres container - if not already started
npm run watch # compile the JS and JSX files into a bundle and recompile as modifications are made (dev mode)

# in a separate terminal
npm run server # runs the django dev server
```

Javascript bundling & minifying is done using webpack to create a single javascript file with all required dependencies in one place. Run `npm run build` to compile the JS and `npm run watch` to watch source files for update and recompile when any changes are made.

## Setting up a DB for development

Use a Postgresql database (recommended) or configure Django to use sqlite3 - see [https://docs.djangoproject.com/en/4.1/ref/databases/].

To create a database `peddleweb_dev`, for example, run the `psql` command:
```
# $ psql -U peddleweb peddleweb_dev
# psql>

CREATE DATABASE peddleweb_dev;
CREATE USER peddleweb WITH ENCRYPTED PASSWORD 'password';
GRANT ALL ON DATABASE peddleweb_dev TO peddleweb;

```

# Distribution
Run `./build.sh` to produce a complete code package with minified CSS/JS under the dist/ folder.

# Troubleshooting miscellaneous issues
If Fringe (Red61) tours are displaying as cancelled when they shouldn't be, eg. if the Red61 system went down:

```
$ npm run shell
>>> Tour.objects.filter(source_row_state='deleted', source='fringe').update(source_row_state='live')

```