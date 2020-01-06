#!/usr/bin/env python
# -*- coding: utf-8 -*-

from telegram import ChatAction
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, RegexHandler
from functools import wraps
import logging, os, requests, random, re, sys

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
					level=logging.DEBUG)

logger = logging.getLogger(__name__)

# Global consts:
MAX_WORDS = 10
NUM_HASHTAGS = 30
PATTERN = re.compile("^[a-zA-Z0-9]*$")
MODE = os.getenv("MODE")
TOKEN = os.getenv("TOKEN")
NAME = os.getenv("NAME")

def send_typing_action(func):
	"""Sends typing action while processing func command."""

	@wraps(func)
	def command_func(*args, **kwargs):
		bot, update = args
		bot.send_chat_action(chat_id=update.effective_message.chat_id, action=ChatAction.TYPING)
		return func(bot, update, **kwargs)

	return command_func

# Define a few command handlers. These usually take the two arguments bot and
# update. Error handlers also receive the raised TelegramError object in error.
def start(bot, update):
	"""Send a message when the command /start is issued."""
	update.message.reply_text('Welcome! Send me /help to know how I can help you')

def help(bot, update):
	"""Send a message when the command /help is issued."""
	update.message.reply_text(
		u'You can send me /gen <list of words> and I will send you the most popular associated hashtags.\nE.g. try to send me "/gen lake mountains sky" and I will send you the associated tags\n'
		u'(max ' + str(MAX_WORDS) + ' words)\n'
		u'You can send me "random" as first word if you want hashtags in random order')

def echo(bot, update):
	"""Echo the user message."""
	update.message.reply_text(update.message.text + ' is not a valid command, please send me /help to know how I can help you.\nE.g. send me "/gen lake mountains sky" and I will send you the associated tags')

def error(bot, update, error):
	"""Log Errors caused by Updates."""
	logger.warning('Update "%s" caused error "%s"', update, error)

@send_typing_action
def hashtags(bot, update, args):
	try:
		if(len(args) == 0):
			update.message.reply_text('Please, send me at least on word.\nE.g. send me "/gen lake mountains sky" and I will send you the associated tags')
			logger.debug('No tags')
			return

		if(args[0] == "random"):
			sort = "random"
			tags = args[1:]
		else:
			sort = "top"
			tags = args

		if(len(tags) > 10):
			update.message.reply_text('Please, send me less than ' + str(MAX_WORDS)  + ' words')
			logger.debug('Too many tags')
			return

		logger.debug('Tags: ' + ' '.join(tags))

		hashtags = generate_hashtags(tags, NUM_HASHTAGS, sort, DEBUG)

		if(len(hashtags) == 0):
			update.message.reply_text('It is not possible to generate hashtags from your words, please, send me another words.\nE.g. send me "/gen lake mountains sky" and I will send you the associated tags')
			return

		update.message.reply_text("•\n•\n•\n•\n•\n" + " ".join(hashtags))

	except (IndexError, ValueError):
		update.message.reply_text('I did not understand, please send me /help to know how I can help you.\nE.g. send me "/gen lake mountains sky" and I will send you the associated tags')

def generate_hashtags(tags, limit=3, sort='top', log_tags=True):
	"""Generate smart hashtags based on https://displaypurposes.com/"""
	"""ranking, banned and spammy tags are filtered out."""

	logger.debug('Generating hashtags for: ' + ' '.join(tags))

	limit = int(NUM_HASHTAGS / len(tags))
	
	hashtags = []

	for tag in tags:
		data = requests.get(
			u'https://d212rkvo8t62el.cloudfront.net/tag/{}'.format(tag)).json()

		if data['tagExists'] is True:
			logger.debug("For " + tag + " tag found " + str(len(data["results"])) + " hashtags")

			# remove non latin tags
			i = 0
			latin_tags = []
			for res_tag in data["results"]:
				if(PATTERN.match(res_tag['tag'])):
					latin_tags.append(res_tag)
				i = i + 1

			logger.debug("For " + tag + " tag found " + str(len(latin_tags)) + " latin hashtags")

			if sort == 'top':
				# sort by ranking
				ordered_tags_by_rank = sorted(
					latin_tags, key=lambda d: d['rank'], reverse=True)
				ranked_tags = (ordered_tags_by_rank[:limit])
				for item in ranked_tags:
					# add smart hashtag to like list
					hashtags.append('#' + item['tag'])

			elif sort == 'random':
				random_tags = random.sample(latin_tags, min(len(latin_tags), limit))
				for item in random_tags:
					hashtags.append('#' + item['tag'])

			if log_tags is True:
				logger.debug('Hashtags for ' + tag +  ': ' + ' '.join(hashtags))
		else:
			logger.debug('Too few results for: ' + tag)

	# delete duplicated tags
	hashtags = list(set(hashtags))

	return hashtags


if MODE == "dev":
	DEBUG = True
	def run(updater):
		# Start the Bot
		updater.start_polling()

		# Run the bot until you press Ctrl-C or the process receives SIGINT,
		# SIGTERM or SIGABRT. This should be used most of the time, since
		# start_polling() is non-blocking and will stop the bot gracefully.
		updater.idle()
elif MODE == "prod":
	DEBUG = False
	def run(updater):
		# Port is given by Heroku
		PORT = os.environ.get('PORT')
		
		# Start the webhook
		updater.start_webhook(listen="0.0.0.0",
							  port=int(PORT),
							  url_path=TOKEN)
		updater.bot.setWebhook("https://{}.herokuapp.com/{}".format(NAME, TOKEN))
		updater.idle()
else:
	logger.error("No MODE specified!")
	sys.exit(1)


if __name__ == "__main__":
	# Start the bot.
	# Create the EventHandler and pass it your bot's token.
	updater = Updater(TOKEN)

	# Get the dispatcher to register handlers
	dp = updater.dispatcher

	# on different commands - answer in Telegram
	dp.add_handler(CommandHandler("start", start))
	dp.add_handler(CommandHandler("help", help))
	dp.add_handler(CommandHandler("gen", hashtags, pass_args=True))
	# on noncommand i.e message - echo the message on Telegram
	dp.add_handler(MessageHandler(Filters.text, echo))
	# log all errors
	dp.add_error_handler(error)

	run(updater)