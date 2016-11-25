import StringIO

from django.conf import settings
from django.http import JsonResponse
from django.utils.translation import ugettext as _

from rest_framework import serializers
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import detail_route

from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.api.viewsets.xform_list_api import XFormListApi
from onadata.apps.api.viewsets.xform_submission_api import XFormSubmissionApi, is_json, dict_lists2strings
from onadata.apps.fsforms.models import FieldSightXF
from onadata.apps.fsforms.serializers import FSXFormListSerializer, FieldSightSubmissionSerializer, \
    FSXFormManifestSerializer
from .fieldsight_logger_tools import dict2xform, safe_create_instance

# 10,000,000 bytes
DEFAULT_CONTENT_LENGTH = getattr(settings, 'DEFAULT_CONTENT_LENGTH', 10000000)


class AssignedXFormListApi(XFormListApi):
    serializer_class = FSXFormListSerializer
    queryset = FieldSightXF.objects.filter(xf__downloadable=True)
    template_name = 'fsforms/assignedFormList.xml'

    def filter_queryset(self, queryset):
        site_id = self.kwargs.get('site_id', None)
        if site_id is None:
            # If no username is specified, the request must be authenticated
            if self.request.user.is_anonymous():
                # raises a permission denied exception, forces authentication
                self.permission_denied(self.request)
            else:
                try:
                    int(site_id)
                except:
                    raise serializers.ValidationError({'site': "Site Id Not Given."})
                else:
                    return super(AssignedXFormListApi, self).filter_queryset(queryset)

                return super(AssignedXFormListApi, self).filter_queryset(queryset)
        site_id = int(site_id)
        queryset = queryset.filter(site__id=site_id)
        return queryset

    @detail_route(methods=['GET'])
    def manifest(self, request, *args, **kwargs):
        self.object = self.get_object()
        object_list = MetaData.objects.filter(data_type='media',
                                              xform=self.object.xf)
        context = self.get_serializer_context()
        serializer = FSXFormManifestSerializer(object_list, many=True,
                                             context=context)

        return Response(serializer.data, headers=self.get_openrosa_headers())

    def list(self, request, *args, **kwargs):
        self.object_list = self.filter_queryset(self.get_queryset())

        serializer = self.get_serializer(self.object_list, many=True)

        return Response(serializer.data, headers=self.get_openrosa_headers())


def create_instance_from_xml(fsxfid, request):
    xml_file_list = request.FILES.pop('xml_submission_file', [])
    xml_file = xml_file_list[0] if len(xml_file_list) else None
    media_files = request.FILES.values()
    return safe_create_instance(fsxfid, xml_file, media_files, None, request)


class FSXFormSubmissionApi(XFormSubmissionApi):
    serializer_class = FieldSightSubmissionSerializer
    template_name = 'fsforms/submission.xml'

    def create(self, request, *args, **kwargs):
        if self.request.user.is_anonymous():
            self.permission_denied(self.request)

        fsxfid = kwargs.get('pk',None)
        siteid = kwargs.get('site_id',None)
        if fsxfid is None or  siteid is None:
            return self.error_response("Site Id Or Form ID Not Given", False, request)
        try:
            siteid =  int(siteid)
            fsxfid = int(fsxfid)
        except:
            return self.error_response("Site Id Or Form ID Not Vaild", False, request)

        if request.method.upper() == 'HEAD':
            return Response(status=status.HTTP_204_NO_CONTENT,
                            headers=self.get_openrosa_headers(request),
                            template_name=self.template_name)

        error, instance = create_instance_from_xml(fsxfid, request)
        # modify create instance

        if error or not instance:
            return self.error_response(error, False, request)

        context = self.get_serializer_context()
        serializer = FieldSightSubmissionSerializer(instance, context=context)
        return Response(serializer.data,
                        headers=self.get_openrosa_headers(request),
                        status=status.HTTP_201_CREATED,
                        template_name=self.template_name)


