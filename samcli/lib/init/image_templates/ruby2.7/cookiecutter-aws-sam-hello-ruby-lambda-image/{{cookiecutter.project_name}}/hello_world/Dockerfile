FROM public.ecr.aws/lambda/ruby:2.7

COPY app.rb Gemfile ./

RUN bundle install

# Command can be overwritten by providing a different command in the template directly.
CMD ["app.lambda_handler"]