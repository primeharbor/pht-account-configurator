# Copyright 2023 - Chris Farris (chris@primeharbor.com) - All Rights Reserved
#

ifndef DEPLOY_BUCKET
$(error DEPLOY_BUCKET is not set)
endif

ifndef version
	export version := $(shell date +%Y%m%d-%H%M)
endif

DEPLOY_PREFIX ?= pht-account-configurator
MANIFEST ?= cloudformation/AccountFactory-Manifest.yaml

# Local to this Makefile Vars
TEMPLATE=cloudformation/AccountFactory-Template.yaml
OUTPUT_TEMPLATE_PREFIX=AccountFactory-Template-Transformed
OUTPUT_TEMPLATE=$(OUTPUT_TEMPLATE_PREFIX)-$(version).yaml
TEMPLATE_URL ?= https://s3.amazonaws.com/$(DEPLOY_BUCKET)/$(DEPLOY_PREFIX)/$(OUTPUT_TEMPLATE)

#
# General Lambda / CFn targets
#
deps:
	cd lambda && pip3 install -r requirements.txt -t .

#
# Deploy Commands
#
package: deps
	@aws cloudformation package --template-file $(TEMPLATE) --s3-bucket $(DEPLOY_BUCKET) --s3-prefix $(DEPLOY_PREFIX)/transform --output-template-file cloudformation/$(OUTPUT_TEMPLATE)  --metadata build_ver=$(version)
	@aws s3 cp cloudformation/$(OUTPUT_TEMPLATE) s3://$(DEPLOY_BUCKET)/$(DEPLOY_PREFIX)/
	rm cloudformation/$(OUTPUT_TEMPLATE)
	@echo "Deploy via $(TEMPLATE_URL)"

deploy: package
ifndef MANIFEST
	$(error MANIFEST is not set)
endif
	cft-deploy -m $(MANIFEST) --template-url $(TEMPLATE_URL) pBucketName=$(DEPLOY_BUCKET) --force

push-config:
	@aws s3 cp account-factory-config.yaml s3://$(DEPLOY_BUCKET)


test-trigger:
ifndef ACCOUNT_ID
	$(error ACCOUNT_ID is not set)
endif
	@scripts/trigger.sh $(MANIFEST) $(ACCOUNT_ID)
# EOF